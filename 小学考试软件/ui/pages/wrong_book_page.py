from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QComboBox, QMessageBox, QProgressBar,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

import config
from data import database as db
from core import ai_engine
from ui.styles import PALETTE


class RetryWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, knowledge_point: str, grade: str, question: dict):
        super().__init__()
        self.kp = knowledge_point
        self.grade = grade
        self.question = question

    def run(self):
        try:
            result = ai_engine.generate_practice(self.kp, self.grade, count=3)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class WrongCard(QFrame):
    retry_clicked = pyqtSignal(str, str, dict)   # kp, grade, question

    def __init__(self, item: dict):
        super().__init__()
        self._item = item
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PALETTE['card']}; border-radius: 10px; "
            f"border: 1px solid {PALETTE['border']}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # 题头
        head = QHBoxLayout()
        kp = item.get("knowledge_point", "")
        kp_lbl = QLabel(kp)
        kp_lbl.setStyleSheet(
            f"background:{PALETTE['primary_light']};color:{PALETTE['primary']};"
            f"border-radius:4px;padding:2px 8px;font-size:12px;font-weight:bold;"
        )
        head.addWidget(kp_lbl)
        head.addSpacing(8)

        diff = item.get("difficulty", "")
        diff_color = {"简单": PALETTE["success"], "中等": PALETTE["primary"],
                      "困难": PALETTE["danger"]}.get(diff, PALETTE["text_hint"])
        diff_lbl = QLabel(diff)
        diff_lbl.setStyleSheet(
            f"background:{diff_color}22;color:{diff_color};"
            f"border-radius:4px;padding:2px 8px;font-size:11px;"
        )
        head.addWidget(diff_lbl)
        head.addStretch()

        date_lbl = QLabel(item.get("submitted_at", "")[:10])
        date_lbl.setStyleSheet(f"font-size:11px;color:{PALETTE['text_hint']};")
        head.addWidget(date_lbl)
        layout.addLayout(head)

        # 题目内容
        content_lbl = QLabel(item.get("content", ""))
        content_lbl.setWordWrap(True)
        content_lbl.setStyleSheet("font-size:13px;")
        layout.addWidget(content_lbl)

        if item.get("options"):
            for opt in item["options"]:
                opt_lbl = QLabel(opt)
                opt_lbl.setStyleSheet(f"font-size:12px;color:{PALETTE['text_secondary']};padding-left:8px;")
                layout.addWidget(opt_lbl)

        # 答案对比
        ans_row = QHBoxLayout()
        wrong_ans = QLabel(f"✗ 我的答案：{item.get('student_answer', '')}")
        wrong_ans.setStyleSheet(f"color:{PALETTE['danger']};font-size:12px;font-weight:bold;")
        ans_row.addWidget(wrong_ans)
        ans_row.addSpacing(16)
        right_ans = QLabel(f"✓ 正确答案：{item.get('answer', '')}")
        right_ans.setStyleSheet(f"color:{PALETTE['success']};font-size:12px;font-weight:bold;")
        ans_row.addWidget(right_ans)
        ans_row.addStretch()

        err_type = item.get("grading", {}).get("error_type", "")
        err_desc = item.get("grading", {}).get("error_desc", "")
        if err_type:
            err_lbl = QLabel(f"错因：{err_type}{'  ' + err_desc if err_desc else ''}")
            err_lbl.setStyleSheet(f"color:{PALETTE['warning']};font-size:11px;")
            ans_row.addWidget(err_lbl)

        layout.addLayout(ans_row)

        # 动图讲解 + 再练按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        anim_btn = QPushButton("🎬  动图讲解")
        anim_btn.setFixedHeight(30)
        anim_btn.setStyleSheet(
            f"QPushButton{{background:{PALETTE['warning_light']};color:{PALETTE['warning']};"
            f"border:none;border-radius:6px;padding:2px 10px;font-size:12px;}}"
        )
        anim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        anim_btn.clicked.connect(lambda: self._open_anim(item))
        btn_row.addWidget(anim_btn)

        retry_btn = QPushButton("🔄  再练同类题")
        retry_btn.setObjectName("btn_secondary")
        retry_btn.setFixedHeight(30)
        retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        retry_btn.clicked.connect(
            lambda: self.retry_clicked.emit(kp, item.get("grade", ""), item)
        )
        btn_row.addWidget(retry_btn)
        layout.addLayout(btn_row)

    def _open_anim(self, item: dict):
        if not config.get("api_key"):
            QMessageBox.warning(self.window(), "API未配置", "请先在【设置】中填写 DeepSeek API Key")
            return
        from ui.widgets.anim_explain_dialog import AnimExplainDialog
        dlg = AnimExplainDialog(item, item.get("grade", "三年级"), self.window())
        dlg.exec()


class WrongBookPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._retry_worker: RetryWorker | None = None
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(32, 28, 32, 24)
        main.setSpacing(16)

        # 页头
        header = QHBoxLayout()
        title = QLabel("错题本")
        title.setObjectName("label_title")
        header.addWidget(title)
        header.addStretch()

        # 知识点过滤
        filter_lbl = QLabel("按知识点筛选：")
        filter_lbl.setStyleSheet(f"color:{PALETTE['text_secondary']};")
        header.addWidget(filter_lbl)
        self._kp_filter = QComboBox()
        self._kp_filter.setMinimumWidth(180)
        self._kp_filter.currentTextChanged.connect(self._refresh_list)
        header.addWidget(self._kp_filter)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{PALETTE['text_hint']};font-size:13px;")
        header.addWidget(self._count_lbl)
        main.addLayout(header)

        # 进度条（再练加载时用）
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.hide()
        main.addWidget(self._progress)

        # 滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 4, 0)
        self._layout.setSpacing(10)
        scroll.setWidget(self._container)
        main.addWidget(scroll, 1)

        self._empty_lbl = QLabel("暂无错题，继续保持！")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{PALETTE['text_hint']};font-size:14px;margin:60px;"
        )

    def on_activate(self):
        self._refresh_filters()
        self._refresh_list()

    def _refresh_filters(self):
        sid = config.get("default_student_id")
        self._kp_filter.blockSignals(True)
        self._kp_filter.clear()
        self._kp_filter.addItem("全部")
        if sid:
            for kp in db.get_wrong_kp_list(int(sid)):
                self._kp_filter.addItem(kp)
        self._kp_filter.blockSignals(False)

    def _refresh_list(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sid = config.get("default_student_id")
        if not sid:
            self._empty_lbl.setParent(None)
            self._layout.addWidget(self._empty_lbl)
            self._count_lbl.setText("")
            return

        kp_sel = self._kp_filter.currentText()
        kp_filter = None if kp_sel == "全部" else kp_sel
        wrongs = db.get_all_wrong_answers(int(sid), kp_filter=kp_filter)

        self._count_lbl.setText(f"共 {len(wrongs)} 条")

        if not wrongs:
            self._layout.addWidget(self._empty_lbl)
            self._layout.addStretch()
            return

        for item in wrongs:
            card = WrongCard(item)
            card.retry_clicked.connect(self._on_retry)
            self._layout.addWidget(card)
        self._layout.addStretch()

    def _on_retry(self, kp: str, grade: str, question: dict):
        if not config.get("api_key"):
            QMessageBox.warning(self, "API未配置", "请先在【设置】中填写 DeepSeek API Key")
            return
        if not kp:
            QMessageBox.warning(self, "提示", "该题缺少知识点信息，无法生成同类题")
            return
        if self._retry_worker and self._retry_worker.isRunning():
            return
        self._progress.show()
        self._retry_worker = RetryWorker(kp, grade or "三年级", question)
        self._retry_worker.finished.connect(self._on_retry_done)
        self._retry_worker.error.connect(self._on_retry_error)
        self._retry_worker.start()

    @pyqtSlot(dict)
    def _on_retry_done(self, data: dict):
        self._progress.hide()
        questions = data.get("questions", [])
        if not questions:
            QMessageBox.information(self, "提示", "未生成到题目，请重试")
            return
        grade = self._retry_worker.grade if self._retry_worker else ""
        mw = self._find_main_window()
        if mw and hasattr(mw, "_practice_page"):
            mw._practice_page.load_retry_questions(questions, grade=grade)
            mw.navigate("practice")

    @pyqtSlot(str)
    def _on_retry_error(self, err: str):
        self._progress.hide()
        QMessageBox.critical(self, "生成失败", err)

    def _find_main_window(self):
        w = self
        while w:
            from ui.main_window import MainWindow
            if isinstance(w, MainWindow):
                return w
            w = w.parent()
        return None
