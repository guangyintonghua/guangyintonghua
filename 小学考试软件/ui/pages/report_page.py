import os
import logging
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTabWidget, QTableWidget,
    QTableWidgetItem, QProgressBar, QMessageBox, QSizePolicy,
    QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor, QFont

from data import database as db
from core.analyzer import mastery_level, mastery_color, get_weak_points, compute_history_trend
from ui.styles import PALETTE
from ui.voice_widget import KPVoiceButton, VoiceControlBar
from utils import pdf_gen
import config

log = logging.getLogger("app.report")

# ── 中文字体 ──────────────────────────────────
for _fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc"]:
    if os.path.exists(_fp):
        fm.fontManager.addfont(_fp)
        _prop = fm.FontProperties(fname=_fp)
        plt.rcParams["font.family"] = _prop.get_name()
        break
plt.rcParams["axes.unicode_minus"] = False


def _canvas(fig: Figure) -> FigureCanvas:
    c = FigureCanvas(fig)
    c.setStyleSheet("background:transparent;")
    return c


# ─────────────────────────────────────────────
class ScoreBanner(QFrame):
    def __init__(self, score: float, total: float, level: str, comment: str):
        super().__init__()
        self.setFixedHeight(130)
        self.setStyleSheet(
            f"background: {PALETTE['card']}; border-radius: 14px; "
            f"border: 1px solid {PALETTE['border']};"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(0)

        pct = round(score / total * 100) if total else 0
        color = (PALETTE["success"] if pct >= 80 else
                 PALETTE["warning"] if pct >= 60 else PALETTE["danger"])

        # 得分
        score_lbl = QLabel(f"{int(score)}")
        score_lbl.setStyleSheet(
            f"font-size: 54px; font-weight: bold; color: {color}; min-width: 90px;"
        )
        layout.addWidget(score_lbl)

        denom = QLabel(f" / {int(total)}")
        denom.setStyleSheet(
            f"font-size: 22px; color: {PALETTE['text_hint']}; padding-top: 26px;"
        )
        layout.addWidget(denom)
        layout.addSpacing(24)

        # 竖分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet(f"color: {PALETTE['border']};")
        layout.addWidget(line)
        layout.addSpacing(24)

        # 信息列
        info = QVBoxLayout()
        info.setSpacing(6)

        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setStyleSheet(
            f"font-size: 26px; font-weight: bold; color: {color};"
        )
        info.addWidget(pct_lbl)

        if level:
            lv_lbl = QLabel(level)
            bg = {"优秀": PALETTE["success"], "良好": PALETTE["primary"],
                  "中等": PALETTE["warning"], "待提高": PALETTE["danger"]}.get(level, PALETTE["primary"])
            lv_lbl.setStyleSheet(
                f"background:{bg}22; color:{bg}; border-radius:4px; "
                f"padding:2px 10px; font-size:13px; font-weight:bold; max-width:80px;"
            )
            info.addWidget(lv_lbl)

        if comment:
            c_lbl = QLabel(comment)
            c_lbl.setWordWrap(True)
            c_lbl.setStyleSheet(f"font-size:12px; color:{PALETTE['text_secondary']};")
            info.addWidget(c_lbl)

        layout.addLayout(info, 1)


# ─────────────────────────────────────────────
class PDFWorker(QThread):
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, student_name, grade, exam_title,
                 graded, analysis, kp_stats, score, total, submitted_at):
        super().__init__()
        self.data = (student_name, grade, exam_title,
                     graded, analysis, kp_stats, score, total, submitted_at)

    def run(self):
        try:
            result = pdf_gen.generate_report_pdf(*self.data)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────
class ReportPage(QWidget):
    open_practice_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sub_id: int | None = None
        self._grade: str = ""
        self._exam_title: str = ""
        self._sub_data: dict = {}
        self._pdf_worker: PDFWorker | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(16)

        # 页头
        header = QHBoxLayout()
        title = QLabel("分析报告")
        title.setObjectName("label_title")
        header.addWidget(title)
        header.addStretch()

        self._export_btn = QPushButton("📄  导出 PDF")
        self._export_btn.setObjectName("btn_secondary")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export_pdf)
        header.addWidget(self._export_btn)

        self._practice_btn = QPushButton("🎯  专项练习")
        self._practice_btn.setObjectName("btn_primary")
        self._practice_btn.setEnabled(False)
        self._practice_btn.clicked.connect(self._on_practice)
        header.addWidget(self._practice_btn)
        layout.addLayout(header)

        # 语音控制栏
        self._voice_bar = VoiceControlBar()
        layout.addWidget(self._voice_bar)

        # 滚动内容区
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content_w = QWidget()
        self._content_l = QVBoxLayout(self._content_w)
        self._content_l.setContentsMargins(0, 0, 4, 0)
        self._content_l.setSpacing(16)
        self._scroll.setWidget(self._content_w)
        layout.addWidget(self._scroll, 1)

        self._empty_lbl = QLabel("完成批改后，详细分析报告将在此展示")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{PALETTE['text_hint']}; font-size:14px; margin:60px;"
        )
        self._content_l.addWidget(self._empty_lbl)

    # ── 加载数据 ──────────────────────────────
    def load_submission(self, sub_id: int):
        self._sub_id = sub_id
        sub = db.get_submission(sub_id)
        if not sub:
            return
        self._sub_data = sub

        exam = db.get_exam(sub["exam_id"]) if sub.get("exam_id") else None
        self._grade = exam.get("grade", "") if exam else ""
        self._exam_title = exam.get("title", "练习") if exam else "练习"

        self._clear()

        graded = sub.get("graded_results", [])
        analysis = sub.get("analysis", {})
        kp_stats = sub.get("kp_stats", {})
        score = sub.get("score", 0)
        total = sub.get("total_score", 100)

        level = analysis.get("summary", {}).get("level", "")
        comment = analysis.get("summary", {}).get("overall_comment", "")

        # 得分横幅
        self._content_l.addWidget(ScoreBanner(score, total, level, comment))

        # Tab 页
        tabs = QTabWidget()
        tabs.setMinimumHeight(500)
        tabs.addTab(self._tab_kp(kp_stats, analysis), "📊  知识点分析")
        tabs.addTab(self._tab_detail(graded), "📋  题目详情")
        tabs.addTab(self._tab_error(analysis, graded), "🔍  错误分析")
        tabs.addTab(self._tab_trend(sub.get("student_id")), "📈  历史趋势")
        self._content_l.addWidget(tabs)

        # 改进建议
        suggestions = analysis.get("study_suggestions", [])
        if suggestions:
            sug_card = self._card()
            sv = QVBoxLayout(sug_card)
            sv.setContentsMargins(20, 16, 20, 16)
            sv.setSpacing(8)
            sv.addWidget(self._section_label("改进建议"))
            for sug in suggestions:
                row = QHBoxLayout()
                pri = QLabel(f"{sug.get('priority','·')}.")
                pri.setStyleSheet(
                    f"color:{PALETTE['primary']};font-weight:bold;min-width:20px;"
                )
                row.addWidget(pri)
                txt = QLabel(f"<b>{sug.get('title','')}</b>  {sug.get('detail','')}")
                txt.setWordWrap(True)
                txt.setStyleSheet("font-size:13px;")
                row.addWidget(txt, 1)
                sv.addLayout(row)
            self._content_l.addWidget(sug_card)

        self._content_l.addStretch()

        # 启用按钮
        weak = get_weak_points(kp_stats)
        if weak:
            self._weakest_kp = weak[0]["knowledge_point"]
            self._practice_btn.setEnabled(True)
        self._export_btn.setEnabled(True)

    # ── Tab: 知识点分析 ───────────────────────
    def _tab_kp(self, kp_stats: dict, analysis: dict) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 左：雷达图 or 柱图
        layout.addWidget(self._build_kp_chart(kp_stats), 1)

        # 右：知识点卡片列表
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(8)

        kp_analysis = analysis.get("kp_analysis", [])
        if not kp_analysis:
            kp_analysis = [
                {
                    "knowledge_point": kp,
                    "mastery_rate": v["rate"],
                    "status": mastery_level(v["rate"]),
                    "wrong_count": v["total"] - v["correct"],
                    "total_count": v["total"],
                    "diagnosis": "",
                }
                for kp, v in sorted(kp_stats.items(), key=lambda x: x[1]["rate"])
            ]

        for kp_data in kp_analysis:
            kp_card = QFrame()
            kp_card.setStyleSheet(
                f"QFrame {{ background:{PALETTE['card']}; border-radius:8px; "
                f"border:1px solid {PALETTE['border']}; }}"
            )
            kl = QVBoxLayout(kp_card)
            kl.setContentsMargins(12, 10, 12, 10)
            kl.setSpacing(5)

            row1 = QHBoxLayout()
            name_lbl = QLabel(kp_data.get("knowledge_point", ""))
            name_lbl.setStyleSheet("font-weight:bold; font-size:13px;")
            row1.addWidget(name_lbl, 1)

            rate = kp_data.get("mastery_rate", 0)
            color = mastery_color(rate)
            status_lbl = QLabel(f"{round(rate*100)}%  {kp_data.get('status', mastery_level(rate))}")
            status_lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:bold;")
            row1.addWidget(status_lbl)

            voice_btn = KPVoiceButton(kp_data.get("knowledge_point", ""), grade=self._grade)
            row1.addWidget(voice_btn)
            kl.addLayout(row1)

            pb = QProgressBar()
            pb.setValue(round(rate * 100))
            pb.setFixedHeight(5)
            pb.setStyleSheet(
                f"QProgressBar{{background:{PALETTE['border']};border-radius:3px;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
            )
            kl.addWidget(pb)

            if kp_data.get("diagnosis"):
                diag = QLabel(kp_data["diagnosis"])
                diag.setStyleSheet(f"font-size:11px;color:{PALETTE['text_hint']};")
                kl.addWidget(diag)

            right_l.addWidget(kp_card)

        right_l.addStretch()
        right_scroll.setWidget(right_w)
        layout.addWidget(right_scroll, 1)
        return w

    def _build_kp_chart(self, kp_stats: dict) -> QWidget:
        names = list(kp_stats.keys())
        rates = [kp_stats[k]["rate"] * 100 for k in names]

        if not names:
            lbl = QLabel("暂无知识点数据")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lbl

        if len(names) >= 3:
            return self._radar_chart(names, rates)
        else:
            return self._bar_chart(names, rates)

    def _radar_chart(self, names: list, rates: list) -> FigureCanvas:
        N = len(names)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]
        vals = rates + rates[:1]

        fig = Figure(figsize=(4.2, 4), facecolor="none")
        ax = fig.add_subplot(111, polar=True)
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_rlabel_position(30)
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(["25", "50", "75", "100%"], fontsize=7, color=PALETTE["text_hint"])
        ax.set_xticks(angles[:-1])
        short = [n if len(n) <= 6 else n[:5] + "…" for n in names]
        ax.set_xticklabels(short, fontsize=8)
        ax.tick_params(pad=6)

        # 参考区域
        ax.fill(angles, [60] * len(angles), alpha=0.08, color=PALETTE["warning"])
        ax.fill(angles, [80] * len(angles), alpha=0.06, color=PALETTE["success"])

        # 数据
        ax.plot(angles, vals, "o-", lw=2, color=PALETTE["primary"])
        ax.fill(angles, vals, alpha=0.2, color=PALETTE["primary"])

        ax.spines["polar"].set_color(PALETTE["border"])
        ax.set_facecolor("none")
        fig.tight_layout(pad=0.5)
        return _canvas(fig)

    def _bar_chart(self, names: list, rates: list) -> FigureCanvas:
        colors = [mastery_color(r / 100) for r in rates]
        short = [n if len(n) <= 8 else n[:7] + "…" for n in names]
        fig = Figure(figsize=(4.2, 3), facecolor="none")
        ax = fig.add_subplot(111)
        ax.barh(short, rates, color=colors, height=0.5, alpha=0.85)
        ax.set_xlim(0, 105)
        ax.axvline(60, color=PALETTE["warning"], ls="--", alpha=0.5, lw=1)
        ax.axvline(80, color=PALETTE["success"], ls="--", alpha=0.5, lw=1)
        ax.set_facecolor("none")
        ax.tick_params(labelsize=9)
        fig.tight_layout(pad=0.4)
        return _canvas(fig)

    # ── Tab: 题目详情 ─────────────────────────
    def _tab_detail(self, graded: list) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        table = QTableWidget(len(graded), 7)
        table.setHorizontalHeaderLabels(
            ["题号", "类型", "知识点", "难度", "学生答案", "正确答案", "结果"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for i, r in enumerate(graded):
            g = r.get("grading", {})
            is_ok = g.get("is_correct", False)
            score_got = g.get("score_got", 0)
            max_s = r.get("score", 0)
            error_type = g.get("error_type") or ""

            items = [
                QTableWidgetItem(f"第{r['id']}题"),
                QTableWidgetItem(r.get("type", "")),
                QTableWidgetItem(r.get("knowledge_point", "")),
                QTableWidgetItem(r.get("difficulty", "")),
                QTableWidgetItem(str(r.get("student_answer", ""))),
                QTableWidgetItem(str(r.get("answer", ""))),
                QTableWidgetItem(
                    f"✓ {score_got}/{max_s}分" if is_ok
                    else f"✗  {score_got}/{max_s}分  {error_type}"
                ),
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col != 2
                                      else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == 6:
                    item.setForeground(
                        QColor(PALETTE["success"]) if is_ok else QColor(PALETTE["danger"])
                    )
                if col == 5:
                    item.setForeground(QColor(PALETTE["success"]))
                table.setItem(i, col, item)

        table.resizeColumnsToContents()
        table.setColumnWidth(2, 160)
        layout.addWidget(table)
        return w

    # ── Tab: 错误分析 ─────────────────────────
    def _tab_error(self, analysis: dict, graded: list) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 错误类型饼图
        error_dist: dict[str, int] = {}
        for r in graded:
            et = r.get("grading", {}).get("error_type")
            if et and et not in ("未作答",):
                error_dist[et] = error_dist.get(et, 0) + 1

        if error_dist:
            fig = Figure(figsize=(4.5, 3.2), facecolor="none")
            ax = fig.add_subplot(111)
            pie_colors = [PALETTE["danger"], PALETTE["warning"],
                          PALETTE["primary"], PALETTE["success"], "#9B59B6"]
            wedges, texts, autotexts = ax.pie(
                error_dist.values(), labels=list(error_dist.keys()),
                autopct="%1.0f%%",
                colors=pie_colors[:len(error_dist)],
                startangle=90, pctdistance=0.75,
            )
            for t in texts:
                t.set_fontsize(9)
            for at in autotexts:
                at.set_fontsize(8)
                at.set_color("white")
            ax.set_title("错误类型分布", fontsize=11)
            fig.tight_layout()
            canvas = _canvas(fig)
            canvas.setFixedHeight(260)
            layout.addWidget(canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        # 错误规律
        patterns = analysis.get("error_patterns", [])
        if patterns:
            layout.addWidget(self._section_label("发现的错误规律"))
            for p in patterns:
                card = self._card()
                pl = QVBoxLayout(card)
                pl.setContentsMargins(16, 12, 16, 12)
                pl.setSpacing(4)
                pat_lbl = QLabel(f"⚠  {p.get('pattern', '')}")
                pat_lbl.setStyleSheet(f"font-weight:bold;color:{PALETTE['warning']};font-size:13px;")
                pl.addWidget(pat_lbl)
                cause_lbl = QLabel(f"根因分析：{p.get('root_cause', '')}")
                cause_lbl.setWordWrap(True)
                cause_lbl.setStyleSheet(f"font-size:12px;color:{PALETTE['text_secondary']};")
                pl.addWidget(cause_lbl)
                layout.addWidget(card)

        layout.addStretch()
        return w

    # ── Tab: 历史趋势 ─────────────────────────
    def _tab_trend(self, student_id: int | None) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        if not student_id:
            layout.addWidget(QLabel("无学生数据"))
            return w

        history = db.get_student_submissions(student_id, limit=10)
        if len(history) < 2:
            hint = QLabel("至少完成 2 次练习后，历史趋势将在此显示")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(f"color:{PALETTE['text_hint']};font-size:13px;margin:40px;")
            layout.addWidget(hint)
            return w

        trend = compute_history_trend(list(reversed(history)))
        dates = trend["dates"]
        rates = trend["rates"]

        fig = Figure(figsize=(7, 3.5), facecolor="none")
        ax = fig.add_subplot(111)

        ax.plot(dates, rates, "o-", color=PALETTE["primary"], lw=2.5,
                markersize=7, markerfacecolor="white",
                markeredgecolor=PALETTE["primary"], markeredgewidth=2)

        # 着色区域
        ax.fill_between(dates, rates, alpha=0.08, color=PALETTE["primary"])
        ax.axhline(60, color=PALETTE["warning"], ls="--", alpha=0.4, lw=1)
        ax.axhline(80, color=PALETTE["success"], ls="--", alpha=0.4, lw=1)
        ax.text(len(dates) - 0.1, 61, "60%", fontsize=8,
                color=PALETTE["warning"], ha="right")
        ax.text(len(dates) - 0.1, 81, "80%", fontsize=8,
                color=PALETTE["success"], ha="right")

        # 标注每个数据点
        for x, y in enumerate(rates):
            ax.annotate(f"{y}%", (x, y), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8,
                        color=PALETTE["primary"])

        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=25, fontsize=8)
        ax.set_ylim(0, 110)
        ax.set_ylabel("正确率 %", fontsize=9)
        ax.set_title("近期得分趋势", fontsize=11, fontweight="bold")
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout(pad=0.6)

        canvas = _canvas(fig)
        layout.addWidget(canvas)

        # 趋势说明
        if len(rates) >= 2:
            delta = rates[-1] - rates[0]
            if delta > 5:
                msg = f"📈  进步显著！正确率提升了 {delta:.1f} 个百分点，继续加油！"
                color = PALETTE["success"]
            elif delta < -5:
                msg = f"📉  最近正确率有所下滑，建议加强薄弱知识点的练习。"
                color = PALETTE["warning"]
            else:
                msg = f"📊  正确率基本稳定，可以尝试挑战更高难度的题目。"
                color = PALETTE["primary"]
            trend_lbl = QLabel(msg)
            trend_lbl.setWordWrap(True)
            trend_lbl.setStyleSheet(
                f"color:{color};font-size:13px;background:{color}11;"
                f"border-radius:6px;padding:8px 12px;"
            )
            layout.addWidget(trend_lbl)

        layout.addStretch()
        return w

    # ── PDF 导出 ──────────────────────────────
    def _on_export_pdf(self):
        if not self._sub_data:
            return
        self._export_btn.setEnabled(False)
        self._export_btn.setText("⏳  生成中...")

        sub = self._sub_data
        student = db.get_student(sub.get("student_id", 0))
        student_name = student["name"] if student else "学生"

        self._pdf_worker = PDFWorker(
            student_name=student_name,
            grade=self._grade,
            exam_title=self._exam_title,
            graded=sub.get("graded_results", []),
            analysis=sub.get("analysis", {}),
            kp_stats=sub.get("kp_stats", {}),
            score=sub.get("score", 0),
            total=sub.get("total_score", 100),
            submitted_at=sub.get("submitted_at", ""),
        )
        self._pdf_worker.finished.connect(self._on_pdf_ready)
        self._pdf_worker.error.connect(self._on_pdf_error)
        self._pdf_worker.start()

    @pyqtSlot(bytes)
    def _on_pdf_ready(self, data: bytes):
        self._export_btn.setEnabled(True)
        self._export_btn.setText("📄  导出 PDF")

        student = db.get_student(self._sub_data.get("student_id", 0))
        name = student["name"] if student else "报告"
        from datetime import datetime
        default = f"{name}_分析报告_{datetime.now().strftime('%Y%m%d')}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "保存分析报告", default, "PDF 文件 (*.pdf)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "导出成功", f"报告已保存至：\n{path}")
            os.startfile(path)

    @pyqtSlot(str)
    def _on_pdf_error(self, err: str):
        self._export_btn.setEnabled(True)
        self._export_btn.setText("📄  导出 PDF")
        log.error(f"PDF export error: {err}")
        QMessageBox.critical(self, "导出失败", f"生成 PDF 时出错：\n{err}")

    def _on_practice(self):
        if hasattr(self, "_weakest_kp"):
            self.open_practice_requested.emit(self._weakest_kp)

    # ── 工具方法 ──────────────────────────────
    def _clear(self):
        while self._content_l.count():
            item = self._content_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame{{background:{PALETTE['card']};border-radius:10px;"
            f"border:1px solid {PALETTE['border']};}}"
        )
        return f

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("label_section")
        return lbl
