from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import date, timedelta

import config
from data import database as db
from ui.styles import PALETTE
from core.analyzer import mastery_level, mastery_color


def _friendly_date(dt_str: str) -> str:
    """把 'YYYY-MM-DD HH:MM:SS' 转成友好显示。同一天保留 HH:MM，跨天保留 MM-DD HH:MM。"""
    if not dt_str or len(dt_str) < 10:
        return dt_str or ""
    day = dt_str[:10]
    time_part = dt_str[11:16] if len(dt_str) >= 16 else ""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if day == today:
        return f"今天 {time_part}"
    if day == yesterday:
        return f"昨天 {time_part}"
    return f"{day[5:]} {time_part}".strip()


def _day_group_label(dt_str: str) -> str:
    if not dt_str or len(dt_str) < 10:
        return "未知日期"
    day = dt_str[:10]
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if day == today:
        return "今天"
    if day == yesterday:
        return "昨天"
    return day


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "",
                 color: str = None, icon: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.setFixedHeight(108)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        # 彩色图标徽章
        if icon:
            ic = QLabel(icon)
            ic.setFixedSize(40, 40)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c = color or PALETTE["primary"]
            ic.setStyleSheet(
                f"background:{c}22;border-radius:10px;font-size:20px;"
            )
            outer.addWidget(ic)

        inner = QVBoxLayout()
        inner.setSpacing(3)

        t = QLabel(title)
        t.setStyleSheet(f"font-size:12px;color:{PALETTE['text_secondary']};")
        inner.addWidget(t)

        v = QLabel(value)
        c = color or PALETTE["text_primary"]
        v.setStyleSheet(f"font-size:26px;font-weight:bold;color:{c};")
        inner.addWidget(v)

        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"font-size:11px;color:{PALETTE['text_hint']};")
            inner.addWidget(s)

        outer.addLayout(inner, 1)


class DateSeparator(QWidget):
    """历史列表中的日期分组分隔线"""

    def __init__(self, label: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 2)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size:12px;font-weight:bold;color:{PALETTE['text_hint']};"
            f"background:{PALETTE['bg']};padding:0 6px;"
        )
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{PALETTE['border']};")

        layout.addWidget(lbl)
        layout.addWidget(line, 1)


class ExamRow(QFrame):
    clicked = pyqtSignal(int)

    # (bg_color, text_color, icon, label)
    _STATUS = {
        "perfect": ("#52B788", "#ffffff", "💯", "满分"),
        "good":    ("#52B788", "#ffffff", "✓",  "优秀"),
        "ok":      ("#4B7BEC", "#ffffff", "≈",  "良好"),
        "pass":    ("#F4A261", "#ffffff", "△",  "及格"),
        "poor":    ("#E07A7A", "#ffffff", "✗",  "加油"),
        "pending": ("#B2BEC3", "#ffffff", "⏳", "未批"),
    }

    def __init__(self, exam: dict, submission: dict | None = None):
        super().__init__()
        self.exam_id = exam["id"]
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        # ── 左侧状态图标徽章 ──────────────────
        if submission and submission.get("total_score", 0) > 0:
            pct = round(submission["score"] / submission["total_score"] * 100)
            if pct >= 100: sk = "perfect"
            elif pct >= 85: sk = "good"
            elif pct >= 70: sk = "ok"
            elif pct >= 60: sk = "pass"
            else:           sk = "poor"
        else:
            pct = None
            sk = "pending"

        bg, fg, ico, lv = self._STATUS[sk]
        badge = QLabel(ico)
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:{bg};border-radius:10px;font-size:16px;color:{fg};"
        )
        row.addWidget(badge)

        # ── 中间：标题 + 元信息 ──────────────
        info = QVBoxLayout()
        info.setSpacing(2)

        title_lbl = QLabel(exam.get("title", "未命名试卷"))
        title_lbl.setStyleSheet(
            f"font-weight:bold;font-size:14px;color:{PALETTE['text_primary']};"
        )
        info.addWidget(title_lbl)

        created_at = exam.get("created_at", "")
        time_str = _friendly_date(created_at)
        grade = exam.get("grade", "")
        sem = exam.get("semester", "")
        meta_text = "  ·  ".join(filter(None, [grade, sem, time_str]))
        meta_lbl = QLabel(meta_text)
        meta_lbl.setStyleSheet(f"font-size:12px;color:{PALETTE['text_hint']};")
        info.addWidget(meta_lbl)

        row.addLayout(info, 1)

        # ── 右侧得分徽章 ─────────────────────
        right = QVBoxLayout()
        right.setSpacing(2)
        right.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        if pct is not None:
            pct_lbl = QLabel(f"{pct}%")
            pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            pct_lbl.setStyleSheet(
                f"font-size:18px;font-weight:bold;color:{bg};"
            )
            right.addWidget(pct_lbl)

            lv_lbl = QLabel(lv)
            lv_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            lv_lbl.setStyleSheet(
                f"font-size:11px;color:{fg};background:{bg};"
                f"border-radius:4px;padding:1px 6px;"
            )
            right.addWidget(lv_lbl)
        else:
            pending_lbl = QLabel("未批改")
            pending_lbl.setStyleSheet(
                f"font-size:12px;color:{fg};background:{bg};"
                f"border-radius:4px;padding:3px 8px;font-weight:bold;"
            )
            right.addWidget(pending_lbl)

        row.addLayout(right)

    def mousePressEvent(self, event):
        self.clicked.emit(self.exam_id)
        super().mousePressEvent(event)


class HomePage(QWidget):
    open_exam_requested = pyqtSignal()
    open_submit_requested = pyqtSignal(int)
    open_report_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(32, 28, 32, 24)
        self._main_layout.setSpacing(20)
        self._build_ui()

    def _build_ui(self):
        # 页头
        header = QHBoxLayout()
        title = QLabel("学习概览")
        title.setObjectName("label_title")
        header.addWidget(title)
        header.addStretch()

        self._weekly_btn = QPushButton("📋  导出周报")
        self._weekly_btn.setObjectName("btn_secondary")
        self._weekly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._weekly_btn.clicked.connect(self._on_export_weekly)
        header.addWidget(self._weekly_btn)

        new_exam_btn = QPushButton("＋  新建试卷")
        new_exam_btn.setObjectName("btn_primary")
        new_exam_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_exam_btn.clicked.connect(self.open_exam_requested)
        header.addWidget(new_exam_btn)
        self._main_layout.addLayout(header)

        # 游戏化横幅（streak + 积分 + 今日目标）
        self._gamify_bar = QFrame()
        self._gamify_bar.setObjectName("card")
        self._gamify_bar.setStyleSheet(
            f"QFrame#card{{background:{PALETTE['card']};border-radius:10px;"
            f"border:1px solid {PALETTE['border']};}}"
        )
        self._gamify_bar.setFixedHeight(64)
        self._gamify_layout = QHBoxLayout(self._gamify_bar)
        self._gamify_layout.setContentsMargins(20, 8, 20, 8)
        self._gamify_layout.setSpacing(0)
        self._main_layout.addWidget(self._gamify_bar)

        # 统计卡片行
        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(16)
        self._main_layout.addLayout(self._stats_row)

        # 徽章行
        self._badge_row_lyt = QHBoxLayout()
        self._badge_row_lyt.setSpacing(8)
        self._main_layout.addLayout(self._badge_row_lyt)

        # 薄弱知识点提示
        self._weak_section = QVBoxLayout()
        weak_title = QLabel("需要加强的知识点")
        weak_title.setObjectName("label_section")
        self._weak_section.addWidget(weak_title)
        self._weak_list_layout = QVBoxLayout()
        self._weak_section.addLayout(self._weak_list_layout)
        self._main_layout.addLayout(self._weak_section)

        # 历史试卷
        history_title = QLabel("历史试卷")
        history_title.setObjectName("label_section")
        self._main_layout.addWidget(history_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_container = QWidget()
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(8)
        scroll.setWidget(self._history_container)
        self._main_layout.addWidget(scroll, 1)

        self.refresh()

    def refresh(self):
        self._clear_layout(self._stats_row)
        self._clear_layout(self._weak_list_layout)
        self._clear_layout(self._history_layout)
        self._clear_layout(self._gamify_layout)
        self._clear_layout(self._badge_row_lyt)

        sid = config.get("default_student_id")
        if not sid:
            empty = QLabel("请先在【设置】中选择或创建学生档案")
            empty.setStyleSheet(f"color: {PALETTE['text_hint']}; font-size: 14px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._stats_row.addWidget(empty)
            return

        student_id = int(sid)
        submissions = db.get_student_submissions(student_id)
        exams = db.get_recent_exams(student_id)
        kp_list = db.get_kp_mastery(student_id)

        # ── 游戏化横幅 ──────────────────────────
        streak = db.get_streak(student_id)
        total_pts = db.get_total_points(student_id)
        daily_done = db.get_daily_questions_done(student_id)
        daily_goal = 20

        streak_lbl = QLabel(f"🔥 连续 {streak} 天")
        streak_lbl.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{PALETTE['warning']};"
        )
        self._gamify_layout.addWidget(streak_lbl)
        self._gamify_layout.addSpacing(24)

        pts_lbl = QLabel(f"⭐ {total_pts} 积分")
        pts_lbl.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{PALETTE['primary']};"
        )
        self._gamify_layout.addWidget(pts_lbl)
        self._gamify_layout.addSpacing(24)

        from PyQt6.QtWidgets import QProgressBar as _PB
        goal_lbl = QLabel(f"今日目标：{daily_done}/{daily_goal} 题")
        goal_lbl.setStyleSheet(f"font-size:13px;color:{PALETTE['text_secondary']};")
        self._gamify_layout.addWidget(goal_lbl)
        goal_bar = _PB()
        goal_bar.setRange(0, daily_goal)
        goal_bar.setValue(min(daily_done, daily_goal))
        goal_bar.setFixedWidth(120)
        goal_bar.setFixedHeight(8)
        goal_bar.setStyleSheet(
            f"QProgressBar{{background:{PALETTE['border']};border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{PALETTE['success']};border-radius:4px;}}"
        )
        goal_bar.setTextVisible(False)
        self._gamify_layout.addWidget(goal_bar)
        self._gamify_layout.addStretch()

        # ── 徽章行 ──────────────────────────────
        badges = db.get_badges(student_id)
        if badges:
            badge_title = QLabel("我的成就：")
            badge_title.setStyleSheet(f"font-size:12px;color:{PALETTE['text_secondary']};")
            self._badge_row_lyt.addWidget(badge_title)
            for b in badges[-8:]:
                b_lbl = QLabel(f"{b['icon']} {b['name']}")
                b_lbl.setToolTip(b["desc"])
                b_lbl.setStyleSheet(
                    f"background:{PALETTE['primary_light']};color:{PALETTE['primary']};"
                    f"border-radius:6px;padding:3px 10px;font-size:12px;"
                )
                self._badge_row_lyt.addWidget(b_lbl)
            self._badge_row_lyt.addStretch()

        # ── 统计卡片 ──────────────────────────
        total_exams = len(exams)
        avg_score = 0.0
        if submissions:
            rates = [s["score"] / s["total_score"] * 100 for s in submissions if s["total_score"]]
            avg_score = round(sum(rates) / len(rates), 1) if rates else 0.0
        weak_count = sum(1 for k in kp_list if k["rate"] < 0.6)
        total_q = sum(k["total_attempts"] for k in kp_list)

        cards = [
            ("练习总数",  str(total_exams), "套试卷",
             PALETTE["primary"], "📋"),
            ("平均得分",  f"{avg_score}%",  "近期综合",
             PALETTE["success"] if avg_score >= 80 else PALETTE["warning"], "📈"),
            ("薄弱知识点", str(weak_count), "待加强",
             PALETTE["danger"] if weak_count > 0 else PALETTE["success"], "⚡"),
            ("累计做题",  str(total_q),    "道",
             PALETTE["text_secondary"], "🎯"),
        ]
        for t, val, sub, color, icon in cards:
            self._stats_row.addWidget(StatCard(t, val, sub, color, icon))

        # ── 薄弱知识点 ────────────────────────
        weak_kps = [k for k in kp_list if k["rate"] < 0.6][:5]
        if weak_kps:
            for kp in weak_kps:
                row = QHBoxLayout()
                name = QLabel(kp["knowledge_point"])
                name.setStyleSheet("font-size: 13px;")
                row.addWidget(name, 1)
                pct = round(kp["rate"] * 100)
                rate_lbl = QLabel(f"{pct}%")
                rate_lbl.setStyleSheet(
                    f"font-weight: bold; color: {mastery_color(kp['rate'])}; min-width: 40px;"
                )
                row.addWidget(rate_lbl)
                level_lbl = QLabel(mastery_level(kp["rate"]))
                level_lbl.setStyleSheet(
                    f"font-size: 12px; color: {mastery_color(kp['rate'])}; min-width: 60px;"
                )
                row.addWidget(level_lbl)
                self._weak_list_layout.addLayout(row)
        else:
            hint = QLabel("暂无薄弱知识点，继续保持！" if kp_list else "完成第一次练习后将显示掌握情况")
            hint.setStyleSheet(f"color: {PALETTE['text_hint']}; font-size: 13px;")
            self._weak_list_layout.addWidget(hint)

        # ── 历史试卷（按日期分组）────────────────
        if not exams:
            empty = QLabel("还没有试卷，点击右上角「新建试卷」开始练习")
            empty.setStyleSheet(f"color:{PALETTE['text_hint']};font-size:13px;")
            self._history_layout.addWidget(empty)
        else:
            # 按日期分组
            from itertools import groupby as _groupby
            sorted_exams = sorted(
                exams[:20],
                key=lambda e: e.get("created_at", ""),
                reverse=True,
            )
            for day_key, day_iter in _groupby(
                sorted_exams, key=lambda e: e.get("created_at", "")[:10]
            ):
                self._history_layout.addWidget(DateSeparator(_day_group_label(day_key)))
                for exam in day_iter:
                    subs = db.get_submissions_for_exam(exam["id"])
                    latest_sub = subs[0] if subs else None
                    row_widget = ExamRow(exam, latest_sub)
                    if latest_sub:
                        sub_id = latest_sub["id"]
                        row_widget.clicked.connect(
                            lambda _, _sid=sub_id: self.open_report_requested.emit(_sid)
                        )
                    else:
                        exam_id = exam["id"]
                        row_widget.clicked.connect(
                            lambda _, _eid=exam_id: self.open_submit_requested.emit(_eid)
                        )
                    self._history_layout.addWidget(row_widget)
            self._history_layout.addStretch()

    def _on_export_weekly(self):
        sid = config.get("default_student_id")
        if not sid:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先在【设置】中选择学生")
            return
        student_id = int(sid)
        student = db.get_student(student_id)
        stats = db.get_weekly_stats(student_id)
        kp_list = db.get_kp_mastery(student_id)
        badges = db.get_badges(student_id)

        try:
            from utils import pdf_gen
            from datetime import datetime
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            import os

            data = pdf_gen.generate_weekly_report_pdf(
                student_name=student["name"] if student else "学生",
                grade=student["grade"] if student else "",
                stats=stats,
                kp_list=kp_list,
                badges=badges,
            )
            default = f"{student['name'] if student else '学生'}_周报_{datetime.now().strftime('%Y%m%d')}.pdf"
            path, _ = QFileDialog.getSaveFileName(self, "保存周报", default, "PDF 文件 (*.pdf)")
            if path:
                with open(path, "wb") as f:
                    f.write(data)
                QMessageBox.information(self, "导出成功", f"周报已保存至：\n{path}")
                os.startfile(path)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "导出失败", str(e))

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def on_activate(self):
        self.refresh()
