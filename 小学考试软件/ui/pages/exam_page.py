from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QScrollArea, QFrame,
    QGroupBox, QGridLayout, QSplitter, QTextEdit, QProgressBar,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont

import json
import config
from data import database as db
from core import ai_engine
from core.knowledge_map import (
    KNOWLEDGE_TREE, GRADES, SEMESTERS, get_units_for_grade_semester, QUESTION_TYPES
)
from ui.styles import PALETTE
from ui.widgets.loading import LoadingOverlay
from utils import pdf_gen


class GenerateWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, grade, semester, topics, type_counts, difficulty):
        super().__init__()
        self.grade = grade
        self.semester = semester
        self.topics = topics
        self.type_counts = type_counts
        self.difficulty = difficulty

    def run(self):
        try:
            result = ai_engine.generate_exam(
                self.grade, self.semester, self.topics,
                self.type_counts, self.difficulty
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ExamPage(QWidget):
    exam_created = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._generated_data: dict | None = None
        self._worker: GenerateWorker | None = None
        self._saved_exam_id: int | None = None
        self._gen_timer: QTimer | None = None
        self._build_ui()
        self._overlay = LoadingOverlay(self)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(20)

        # 页头
        title = QLabel("智能出题")
        title.setObjectName("label_title")
        main_layout.addWidget(title)

        # 分割布局：左配置 | 右预览
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        # ── 左侧：配置区 ──────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 4, 12, 4)
        left_layout.setSpacing(12)

        # 年级/册
        grade_card = self._make_card("基本配置")
        grade_grid = QGridLayout()
        grade_grid.setSpacing(12)

        grade_grid.addWidget(QLabel("年级："), 0, 0)
        self._grade_combo = QComboBox()
        self._grade_combo.addItems(GRADES)
        default_grade = config.get("default_grade") or "三年级"
        sid = config.get("default_student_id")
        if sid:
            s = db.get_student(int(sid))
            if s and s.get("grade") in GRADES:
                default_grade = s["grade"]
        self._grade_combo.setCurrentText(default_grade)
        self._grade_combo.currentTextChanged.connect(self._on_grade_changed)
        grade_grid.addWidget(self._grade_combo, 0, 1)

        grade_grid.addWidget(QLabel("册："), 1, 0)
        self._semester_combo = QComboBox()
        self._semester_combo.addItems(SEMESTERS)
        self._semester_combo.currentTextChanged.connect(self._on_semester_changed)
        grade_grid.addWidget(self._semester_combo, 1, 1)

        grade_card.layout().addLayout(grade_grid)

        # 地区 / 教材版本 提示行（可点击跳转设置）
        self._region_info_lbl = QLabel()
        self._region_info_lbl.setWordWrap(True)
        self._region_info_lbl.setStyleSheet(
            f"font-size: 12px; color: {PALETTE['primary']};"
            f"background: {PALETTE['primary_light']}; border-radius: 6px;"
            f"padding: 5px 10px;"
        )
        self._region_info_lbl.setToolTip("点击前往设置修改地区和教材版本")
        self._region_info_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._region_info_lbl.mousePressEvent = lambda _: self._go_to_settings()
        grade_card.layout().addWidget(self._region_info_lbl)
        self._refresh_region_label()

        left_layout.addWidget(grade_card)

        # 知识点选择
        kp_card = self._make_card("知识点范围")

        # 全选/清空按钮行放在列表上方
        _kp_btn_style = (
            f"QPushButton {{ background: {PALETTE['primary_light']}; color: {PALETTE['primary']};"
            f"border: 1px solid {PALETTE['primary']}; border-radius: 6px;"
            f"padding: 3px 14px; font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {PALETTE['primary']}; color: white; }}"
        )
        select_row = QHBoxLayout()
        select_row.setSpacing(6)
        all_btn = QPushButton("全选")
        all_btn.setStyleSheet(_kp_btn_style)
        all_btn.setFixedHeight(30)
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.clicked.connect(self._select_all_kp)
        none_btn = QPushButton("清空")
        none_btn.setStyleSheet(_kp_btn_style)
        none_btn.setFixedHeight(30)
        none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        none_btn.clicked.connect(self._deselect_all_kp)
        select_row.addWidget(all_btn)
        select_row.addWidget(none_btn)
        select_row.addStretch()
        kp_card.layout().addLayout(select_row)

        self._kp_scroll = QScrollArea()
        self._kp_scroll.setWidgetResizable(True)
        self._kp_scroll.setFixedHeight(190)
        self._kp_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._kp_container = QWidget()
        self._kp_layout = QVBoxLayout(self._kp_container)
        self._kp_layout.setContentsMargins(0, 0, 0, 0)
        self._kp_layout.setSpacing(4)
        self._kp_scroll.setWidget(self._kp_container)
        kp_card.layout().addWidget(self._kp_scroll)
        left_layout.addWidget(kp_card)

        # 难度配置
        diff_card = self._make_card("难度分布")

        adaptive_row = QHBoxLayout()
        self._adaptive_check = QCheckBox("自适应难度")
        self._adaptive_check.setToolTip(
            "根据历史答题成绩与所选知识点掌握度自动推荐难度分布"
        )
        self._adaptive_check.toggled.connect(self._on_adaptive_toggled)
        adaptive_row.addWidget(self._adaptive_check)
        adaptive_row.addStretch()
        diff_card.layout().addLayout(adaptive_row)

        diff_grid = QGridLayout()
        diff_grid.setSpacing(8)
        labels = ["简单 %", "中等 %", "困难 %"]
        defaults = [40, 40, 20]
        self._diff_spins: list[QSpinBox] = []
        for i, (lbl, val) in enumerate(zip(labels, defaults)):
            diff_grid.addWidget(QLabel(lbl), 0, i)
            sp = QSpinBox()
            sp.setRange(0, 100)
            sp.setValue(val)
            sp.setFixedWidth(70)
            sp.valueChanged.connect(self._update_diff_hint)
            self._diff_spins.append(sp)
            diff_grid.addWidget(sp, 1, i)
        diff_card.layout().addLayout(diff_grid)

        self._diff_hint = QLabel("✓ 合计：100%")
        self._diff_hint.setStyleSheet(
            f"color: {PALETTE['success']}; font-size: 13px; font-weight: bold;"
            f"background: {PALETTE['success_light']}; border-radius: 6px;"
            f"padding: 4px 10px; margin-top: 6px;"
        )
        self._diff_hint.setFixedHeight(30)
        diff_card.layout().addWidget(self._diff_hint)

        self._adaptive_info = QLabel("")
        self._adaptive_info.setStyleSheet(
            f"color: {PALETTE['primary']}; font-size: 12px;"
            f"background: {PALETTE['primary_light']}; border-radius: 6px;"
            f"padding: 4px 10px; margin-top: 2px;"
        )
        self._adaptive_info.setWordWrap(True)
        self._adaptive_info.hide()
        diff_card.layout().addWidget(self._adaptive_info)

        left_layout.addWidget(diff_card)

        left_layout.addStretch()

        self._gen_btn = QPushButton("✨  AI 生成试卷")
        self._gen_btn.setObjectName("btn_primary")
        self._gen_btn.setFixedHeight(44)
        self._gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_btn.clicked.connect(self._on_generate)
        left_layout.addWidget(self._gen_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.hide()
        left_layout.addWidget(self._progress)

        splitter.addWidget(left_widget)

        # ── 右侧：预览区 ──────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(12)

        preview_header = QHBoxLayout()
        preview_lbl = QLabel("试卷预览")
        preview_lbl.setObjectName("label_section")
        preview_header.addWidget(preview_lbl)
        preview_header.addStretch()

        self._score_label = QLabel("")
        self._score_label.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 13px;")
        preview_header.addWidget(self._score_label)
        right_layout.addLayout(preview_header)

        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setStyleSheet(
            f"font-family: 'Microsoft YaHei UI'; font-size: 14px; line-height: 1.6;"
            f"background: {PALETTE['card']}; border-radius: 12px;"
        )
        self._preview_text.setPlaceholderText("配置好参数后点击「AI 生成试卷」，题目将在此预览...")
        right_layout.addWidget(self._preview_text, 1)

        # 底部按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._export_btn = QPushButton("📄  导出试卷")
        self._export_btn.setObjectName("btn_secondary")
        self._export_btn.setEnabled(False)
        self._export_btn.setToolTip("导出为可打印的 PDF 试卷")
        self._export_btn.clicked.connect(self._on_export_pdf)
        btn_row.addWidget(self._export_btn)

        self._save_btn = QPushButton("💾  保存")
        self._save_btn.setObjectName("btn_secondary")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        self._next_btn = QPushButton("📷  去批改  →")
        self._next_btn.setObjectName("btn_primary")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._on_next)
        btn_row.addWidget(self._next_btn)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 680])

        self._kp_checkboxes: list[QCheckBox] = []
        self._refresh_kp_list()
        self._update_diff_hint()

    def _make_card(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setObjectName("card")
        box.setStyleSheet(
            f"QGroupBox {{ background: {PALETTE['card']}; border: 1px solid {PALETTE['border']};"
            f"border-radius: 10px; margin-top: 14px; padding: 8px 10px 10px 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 12px; top: -5px;"
            f"color: {PALETTE['text_secondary']}; font-size: 12px; }}"
        )
        layout = QVBoxLayout()
        layout.setSpacing(8)
        box.setLayout(layout)
        return box

    def _update_diff_hint(self):
        total = sum(sp.value() for sp in self._diff_spins)
        base = "font-size: 13px; font-weight: bold; border-radius: 6px; padding: 4px 10px; margin-top: 6px;"
        if total == 100:
            self._diff_hint.setText("✓ 合计：100%")
            self._diff_hint.setStyleSheet(
                f"color: {PALETTE['success']}; background: {PALETTE['success_light']}; {base}"
            )
        else:
            self._diff_hint.setText(f"⚠ 合计：{total}%（需等于 100%）")
            self._diff_hint.setStyleSheet(
                f"color: {PALETTE['warning']}; background: {PALETTE['warning_light']}; {base}"
            )

    def _refresh_region_label(self):
        region = config.get("region") or "全国通用"
        tb = config.get("textbook_version") or "人教版（PEP）"
        self._region_info_lbl.setText(f"📍 {region}  ·  📖 {tb}  （点击可修改）")

    def _go_to_settings(self):
        w = self
        while w:
            from ui.main_window import MainWindow
            if isinstance(w, MainWindow):
                w.navigate("settings")
                return
            w = w.parent()

    # ── 自适应难度 ────────────────────────────────

    def on_activate(self):
        self._refresh_region_label()
        self._maybe_auto_enable_adaptive()

    def _maybe_auto_enable_adaptive(self):
        """首次进入页面时，若学生有答题记录则自动开启自适应。"""
        sid = config.get("default_student_id")
        if not sid:
            return
        subs = db.get_student_submissions(int(sid), limit=1)
        if subs and not self._adaptive_check.isChecked():
            self._adaptive_check.setChecked(True)

    def _on_adaptive_toggled(self, checked: bool):
        for sp in self._diff_spins:
            sp.setEnabled(not checked)
        if checked:
            self._refresh_adaptive_difficulty()
            self._adaptive_info.show()
        else:
            self._adaptive_info.hide()

    def _refresh_adaptive_difficulty(self):
        """查询历史数据，计算并应用自适应难度分布。"""
        sid = config.get("default_student_id")
        if not sid:
            self._adaptive_info.setText("暂无学生数据，使用默认分布 40/40/20")
            return

        topics = self._get_selected_topics()
        result = db.get_adaptive_difficulty(int(sid), topics)

        self._diff_spins[0].setValue(result["easy"])
        self._diff_spins[1].setValue(result["medium"])
        self._diff_spins[2].setValue(result["hard"])

        parts = []
        if result["exam_count"] > 0:
            pct = round(result["avg_score_rate"] * 100)
            parts.append(f"近 {result['exam_count']} 次均分 {pct}%")
        if result["kp_count"] > 0:
            pct = round(result["avg_kp_rate"] * 100)
            parts.append(f"{result['kp_count']} 个知识点掌握度 {pct}%")

        if parts:
            self._adaptive_info.setText("基于" + "、".join(parts) + " 自动推荐")
        else:
            self._adaptive_info.setText("暂无历史记录，使用默认分布 40/40/20")

    def _on_grade_changed(self):
        self._refresh_kp_list()
        if self._adaptive_check.isChecked():
            self._refresh_adaptive_difficulty()

    def _on_semester_changed(self):
        self._refresh_kp_list()
        if self._adaptive_check.isChecked():
            self._refresh_adaptive_difficulty()

    def _refresh_kp_list(self):
        # 清空
        while self._kp_layout.count():
            item = self._kp_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._kp_checkboxes.clear()

        grade = self._grade_combo.currentText()
        semester = self._semester_combo.currentText()
        units = get_units_for_grade_semester(grade, semester)

        for unit, kps in units.items():
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet(f"font-weight: bold; color: {PALETTE['text_secondary']}; "
                                    "font-size: 12px; margin-top: 6px;")
            self._kp_layout.addWidget(unit_lbl)
            for kp in kps:
                cb = QCheckBox(kp)
                cb.setChecked(True)
                self._kp_layout.addWidget(cb)
                self._kp_checkboxes.append(cb)

    def _select_all_kp(self):
        for cb in self._kp_checkboxes:
            cb.setChecked(True)

    def _deselect_all_kp(self):
        for cb in self._kp_checkboxes:
            cb.setChecked(False)

    def _get_selected_topics(self) -> list[str]:
        return [cb.text() for cb in self._kp_checkboxes if cb.isChecked()]

    def _get_type_counts(self) -> dict:
        return {ttype: (info["default_count"], info["default_score"])
                for ttype, info in QUESTION_TYPES.items()}

    def _on_generate(self):
        topics = self._get_selected_topics()
        if not topics:
            QMessageBox.warning(self, "提示", "请至少选择一个知识点")
            return

        if not config.get("api_key"):
            QMessageBox.warning(self, "API未配置", "请先在【设置】中填写 DeepSeek API Key")
            return

        diff = tuple(sp.value() for sp in self._diff_spins)
        if sum(diff) != 100:
            QMessageBox.warning(self, "配置错误", f"难度分布合计为 {sum(diff)}%，需调整为 100%")
            return

        type_counts = self._get_type_counts()

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("正在生成...")
        self._progress.show()
        self._preview_text.setPlaceholderText("AI 正在思考中，请稍候...")
        self._preview_text.clear()
        self._overlay.show_loading("AI 正在生成试题，约需 30-60 秒，请耐心等待...")

        self._worker = GenerateWorker(
            self._grade_combo.currentText(),
            self._semester_combo.currentText(),
            topics, type_counts, diff
        )
        self._worker.finished.connect(self._on_generated)
        self._worker.error.connect(self._on_generate_error)
        self._worker.start()

        # 90 秒 wall-clock 超时，防止 API 长时间挂起
        if self._gen_timer:
            self._gen_timer.stop()
        self._gen_timer = QTimer(self)
        self._gen_timer.setSingleShot(True)
        self._gen_timer.timeout.connect(self._on_generate_timeout)
        self._gen_timer.start(90_000)

    def _stop_gen_timer(self):
        if self._gen_timer:
            self._gen_timer.stop()
            self._gen_timer = None

    def _on_generate_timeout(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        self._on_generate_error("生成超时（90秒），请检查网络或稍后重试")

    @pyqtSlot(dict)
    def _on_generated(self, data: dict):
        self._stop_gen_timer()
        self._overlay.hide_loading()
        self._progress.hide()
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("✨  AI 生成试卷")
        self._generated_data = data
        self._saved_exam_id = None  # 新试卷，重置保存状态

        questions = data.get("questions", [])
        total = data.get("total_score", sum(q["score"] for q in questions))
        self._score_label.setText(f"共 {len(questions)} 题 · 满分 {total} 分")

        lines = []
        type_groups: dict[str, list] = {}
        for q in questions:
            type_groups.setdefault(q["type"], []).append(q)

        for qtype, qs in type_groups.items():
            lines.append(f"\n【{qtype}】")
            lines.append("─" * 40)
            for q in qs:
                lines.append(
                    f"\n第{q['id']}题  [{q.get('difficulty','中等')}]  "
                    f"[{q.get('knowledge_point','')}]  ({q['score']}分)"
                )
                lines.append(q["content"])
                if q.get("options"):
                    for opt in q["options"]:
                        lines.append(f"  {opt}")
                lines.append("")  # 留空作答区间隔

        self._preview_text.setText("\n".join(lines))
        self._export_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._next_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_generate_error(self, err: str):
        self._stop_gen_timer()
        self._overlay.hide_loading()
        self._progress.hide()
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("✨  AI 生成试卷")
        QMessageBox.critical(self, "生成失败", f"出错：\n{err}")

    def _on_export_pdf(self):
        if not self._generated_data:
            return
        questions = self._generated_data.get("questions", [])
        grade = self._grade_combo.currentText()
        semester = self._semester_combo.currentText()
        topics = self._get_selected_topics()
        title = f"{grade}{semester}·{topics[0] if topics else '综合'}练习卷"
        sid = config.get("default_student_id")
        student_name = ""
        if sid:
            s = db.get_student(int(sid))
            if s:
                student_name = s["name"]
        try:
            pdf_bytes = pdf_gen.generate_exam_pdf(
                questions=questions, title=title,
                grade=grade, semester=semester,
                student_name=student_name, show_answers=False,
            )
            from datetime import datetime
            default = f"{grade}{semester}练习卷_{datetime.now().strftime('%Y%m%d')}.pdf"
            import os
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "保存试卷 PDF", default, "PDF 文件 (*.pdf)"
            )
            if path:
                with open(path, "wb") as f:
                    f.write(pdf_bytes)
                QMessageBox.information(self, "导出成功", f"试卷已保存：\n{path}")
                os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _on_save(self):
        if not self._generated_data:
            return
        sid = config.get("default_student_id")
        if not sid:
            QMessageBox.warning(self, "提示", "请先在设置中选择学生")
            return
        if self._saved_exam_id is None:
            self._saved_exam_id = self._do_save(int(sid))
        QMessageBox.information(self, "已保存", "试卷已保存，可前往批改页上传答卷")

    def _do_save(self, student_id: int) -> int:
        data = self._generated_data
        questions = data.get("questions", [])
        total = data.get("total_score", sum(q["score"] for q in questions))
        grade = self._grade_combo.currentText()
        semester = self._semester_combo.currentText()
        topics = self._get_selected_topics()
        title = f"{grade}{semester} · {topics[0] if topics else '综合'}等"

        exam_id = db.save_exam(
            student_id=student_id,
            title=title,
            grade=grade,
            semester=semester,
            topics=topics,
            questions=questions,
            total_score=total,
        )
        return exam_id

    def _on_next(self):
        if not self._generated_data:
            return
        sid = config.get("default_student_id")
        if not sid:
            QMessageBox.warning(self, "提示", "请先在设置中选择学生")
            return
        if self._saved_exam_id is None:
            self._saved_exam_id = self._do_save(int(sid))
        self.exam_created.emit(self._saved_exam_id)
