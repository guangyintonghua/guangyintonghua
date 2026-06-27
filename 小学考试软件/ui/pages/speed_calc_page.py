import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QSpinBox, QLineEdit, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeyEvent

import config
from data import database as db
from ui.styles import PALETTE


# ── 本地口算题生成 ────────────────────────────

_GRADE_CONFIG = {
    "一年级": {"ops": ["+", "-"],               "max_a": 20,   "max_b": 10},
    "二年级": {"ops": ["+", "-", "×"],           "max_a": 100,  "max_b": 20},
    "三年级": {"ops": ["+", "-", "×", "÷"],      "max_a": 1000, "max_b": 50},
    "四年级": {"ops": ["+", "-", "×", "÷"],      "max_a": 9999, "max_b": 99},
    "五年级": {"ops": ["+", "-", "×", "÷"],      "max_a": 9999, "max_b": 999},
    "六年级": {"ops": ["+", "-", "×", "÷"],      "max_a": 9999, "max_b": 999},
}


def _gen_question(grade: str) -> dict:
    cfg = _GRADE_CONFIG.get(grade, _GRADE_CONFIG["三年级"])
    op = random.choice(cfg["ops"])
    max_a, max_b = cfg["max_a"], cfg["max_b"]

    if op == "+":
        a = random.randint(1, max_a)
        b = random.randint(1, max_b)
        ans = a + b
    elif op == "-":
        a = random.randint(1, max_a)
        b = random.randint(1, min(a, max_b))
        ans = a - b
    elif op == "×":
        a = random.randint(2, min(12, max_b))
        b = random.randint(2, min(12, max_b))
        ans = a * b
    else:  # ÷
        b = random.randint(2, min(9, max_b))
        ans = random.randint(1, max_a // b)
        a = ans * b

    return {"expr": f"{a} {op} {b} =", "answer": ans}


# ── 页面 ─────────────────────────────────────

class SpeedCalcPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._questions: list[dict] = []
        self._current_idx: int = 0
        self._correct: int = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._seconds_left: int = 0
        self._running: bool = False
        self._grade: str = "三年级"
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(32, 28, 32, 24)
        main.setSpacing(20)

        title = QLabel("口算速练")
        title.setObjectName("label_title")
        main.addWidget(title)

        # ── 配置卡 ──
        cfg_card = QFrame()
        cfg_card.setObjectName("card")
        cfg_card.setStyleSheet(
            f"QFrame#card{{background:{PALETTE['card']};border-radius:10px;"
            f"border:1px solid {PALETTE['border']};}}"
        )
        cfg_layout = QHBoxLayout(cfg_card)
        cfg_layout.setContentsMargins(20, 14, 20, 14)
        cfg_layout.setSpacing(20)

        cfg_layout.addWidget(QLabel("题目数量："))
        self._count_spin = QSpinBox()
        self._count_spin.setRange(5, 50)
        self._count_spin.setValue(20)
        self._count_spin.setFixedWidth(70)
        cfg_layout.addWidget(self._count_spin)

        cfg_layout.addWidget(QLabel("时间限制："))
        self._time_combo = QComboBox()
        for label in ["1 分钟", "2 分钟", "3 分钟", "5 分钟", "不限时"]:
            self._time_combo.addItem(label)
        self._time_combo.setCurrentText("3 分钟")
        cfg_layout.addWidget(self._time_combo)

        cfg_layout.addStretch()

        self._start_btn = QPushButton("▶  开始练习")
        self._start_btn.setObjectName("btn_primary")
        self._start_btn.setFixedHeight(38)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._start)
        cfg_layout.addWidget(self._start_btn)
        main.addWidget(cfg_card)

        # ── 练习区 ──
        self._practice_frame = QFrame()
        pf_layout = QVBoxLayout(self._practice_frame)
        pf_layout.setContentsMargins(0, 0, 0, 0)
        pf_layout.setSpacing(20)

        # 计时器 + 进度
        info_row = QHBoxLayout()
        self._timer_lbl = QLabel("3:00")
        self._timer_lbl.setStyleSheet(
            f"font-size:32px;font-weight:bold;color:{PALETTE['primary']};"
        )
        info_row.addWidget(self._timer_lbl)
        info_row.addStretch()

        self._prog_lbl = QLabel("0 / 20")
        self._prog_lbl.setStyleSheet(
            f"font-size:20px;font-weight:bold;color:{PALETTE['text_secondary']};"
        )
        info_row.addWidget(self._prog_lbl)
        pf_layout.addLayout(info_row)

        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 20)
        self._prog_bar.setValue(0)
        self._prog_bar.setFixedHeight(6)
        pf_layout.addWidget(self._prog_bar)

        # 大题目展示
        self._q_card = QFrame()
        self._q_card.setStyleSheet(
            f"background:{PALETTE['card']};border-radius:16px;"
            f"border:1px solid {PALETTE['border']};"
        )
        q_inner = QVBoxLayout(self._q_card)
        q_inner.setContentsMargins(40, 40, 40, 40)
        q_inner.setSpacing(24)

        self._expr_lbl = QLabel("准备好了吗？")
        self._expr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._expr_lbl.setStyleSheet(
            f"font-size:48px;font-weight:bold;color:{PALETTE['text_primary']};"
        )
        q_inner.addWidget(self._expr_lbl)

        self._answer_edit = QLineEdit()
        self._answer_edit.setPlaceholderText("输入答案，按 Enter 确认")
        self._answer_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._answer_edit.setStyleSheet(
            f"font-size:28px;font-weight:bold;border:2px solid {PALETTE['primary']};"
            f"border-radius:10px;padding:10px;background:{PALETTE['card']};"
        )
        self._answer_edit.returnPressed.connect(self._submit_answer)
        self._answer_edit.setEnabled(False)
        q_inner.addWidget(self._answer_edit)

        self._feedback_lbl = QLabel("")
        self._feedback_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feedback_lbl.setStyleSheet("font-size:20px;font-weight:bold;")
        self._feedback_lbl.setFixedHeight(32)
        q_inner.addWidget(self._feedback_lbl)

        pf_layout.addWidget(self._q_card, 1)

        self._stop_btn = QPushButton("■  结束练习")
        self._stop_btn.setObjectName("btn_secondary")
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.clicked.connect(self._finish)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._stop_btn)
        pf_layout.addLayout(btn_row)

        self._practice_frame.hide()
        main.addWidget(self._practice_frame, 1)

        # ── 结果区 ──
        self._result_frame = QFrame()
        rf_layout = QVBoxLayout(self._result_frame)
        rf_layout.setContentsMargins(0, 0, 0, 0)
        rf_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rf_layout.setSpacing(16)

        self._result_score_lbl = QLabel("")
        self._result_score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_score_lbl.setStyleSheet(
            f"font-size:64px;font-weight:bold;color:{PALETTE['primary']};"
        )
        rf_layout.addWidget(self._result_score_lbl)

        self._result_detail_lbl = QLabel("")
        self._result_detail_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_detail_lbl.setStyleSheet(
            f"font-size:18px;color:{PALETTE['text_secondary']};"
        )
        rf_layout.addWidget(self._result_detail_lbl)

        self._result_pts_lbl = QLabel("")
        self._result_pts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_pts_lbl.setStyleSheet(
            f"font-size:16px;color:{PALETTE['success']};font-weight:bold;"
            f"background:{PALETTE['success_light']};border-radius:8px;padding:8px 20px;"
        )
        rf_layout.addWidget(self._result_pts_lbl)

        retry_btn = QPushButton("🔄  再练一次")
        retry_btn.setObjectName("btn_primary")
        retry_btn.setFixedHeight(42)
        retry_btn.setFixedWidth(160)
        retry_btn.clicked.connect(self._reset)
        rf_layout.addWidget(retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._result_frame.hide()
        main.addWidget(self._result_frame, 1)

        main.addStretch()

    def on_activate(self):
        sid = config.get("default_student_id")
        if sid:
            s = db.get_student(int(sid))
            if s:
                self._grade = s["grade"]

    def _start(self):
        self._grade = "三年级"
        sid = config.get("default_student_id")
        if sid:
            s = db.get_student(int(sid))
            if s:
                self._grade = s["grade"]

        count = self._count_spin.value()
        self._questions = [_gen_question(self._grade) for _ in range(count)]
        self._current_idx = 0
        self._correct = 0
        self._running = True

        time_text = self._time_combo.currentText()
        if time_text == "不限时":
            self._seconds_left = -1
            self._timer_lbl.setText("∞")
        else:
            mins = int(time_text.split()[0])
            self._seconds_left = mins * 60
            self._timer.start(1000)

        self._prog_bar.setMaximum(count)
        self._prog_bar.setValue(0)
        self._start_btn.hide()
        self._result_frame.hide()
        self._practice_frame.show()
        self._show_question()

    def _show_question(self):
        if self._current_idx >= len(self._questions):
            self._finish()
            return
        q = self._questions[self._current_idx]
        self._expr_lbl.setText(q["expr"])
        self._answer_edit.clear()
        self._answer_edit.setEnabled(True)
        self._answer_edit.setFocus()
        self._feedback_lbl.setText("")
        self._prog_lbl.setText(f"{self._current_idx + 1} / {len(self._questions)}")
        self._prog_bar.setValue(self._current_idx)

    def _submit_answer(self):
        if not self._running or self._current_idx >= len(self._questions):
            return
        text = self._answer_edit.text().strip()
        if not text:
            return
        try:
            user_ans = int(text)
        except ValueError:
            self._feedback_lbl.setText("请输入整数")
            self._feedback_lbl.setStyleSheet(f"font-size:20px;color:{PALETTE['warning']};font-weight:bold;")
            return

        correct_ans = self._questions[self._current_idx]["answer"]
        if user_ans == correct_ans:
            self._correct += 1
            self._feedback_lbl.setText("✓ 正确！")
            self._feedback_lbl.setStyleSheet(
                f"font-size:20px;color:{PALETTE['success']};font-weight:bold;"
            )
        else:
            self._feedback_lbl.setText(f"✗ 答案是 {correct_ans}")
            self._feedback_lbl.setStyleSheet(
                f"font-size:20px;color:{PALETTE['danger']};font-weight:bold;"
            )

        self._answer_edit.setEnabled(False)
        self._current_idx += 1
        QTimer.singleShot(600, self._show_question)

    def _tick(self):
        if self._seconds_left <= 0:
            self._timer.stop()
            self._finish()
            return
        self._seconds_left -= 1
        m, s = divmod(self._seconds_left, 60)
        self._timer_lbl.setText(f"{m}:{s:02d}")
        if self._seconds_left <= 10:
            self._timer_lbl.setStyleSheet(
                f"font-size:32px;font-weight:bold;color:{PALETTE['danger']};"
            )

    def _finish(self):
        self._timer.stop()
        self._running = False
        self._answer_edit.setEnabled(False)

        total = len(self._questions)
        done = min(self._current_idx, total)
        rate = round(self._correct / done * 100) if done > 0 else 0

        color = (PALETTE["success"] if rate >= 80 else
                 PALETTE["warning"] if rate >= 60 else PALETTE["danger"])

        self._result_score_lbl.setText(f"{rate}%")
        self._result_score_lbl.setStyleSheet(
            f"font-size:64px;font-weight:bold;color:{color};"
        )
        self._result_detail_lbl.setText(
            f"答对 {self._correct} / {done} 题  · 共 {total} 题"
        )

        # 积分 & 打卡
        pts = self._correct * 1
        sid = config.get("default_student_id")
        badge_msg = ""
        if sid:
            student_id = int(sid)
            db.award_points(student_id, pts, "口算速练")
            db.checkin_today(student_id, done)
            if done == 20 and self._correct == 20:
                with db.get_conn() as _conn:
                    if db._award_badge(_conn, student_id, "speed_ace"):
                        badge_msg = "\n🚀 新成就解锁：口算飞人！"
            newly = db.check_and_award_badges(student_id)
            if newly and not badge_msg:
                icon, name, _ = db.BADGE_DEFS.get(newly[0], ("🏅", newly[0], ""))
                badge_msg = f"\n{icon} 新成就解锁：{name}！"

        self._result_pts_lbl.setText(f"+{pts} 积分{badge_msg}")
        self._result_pts_lbl.setVisible(pts > 0 or badge_msg)

        self._practice_frame.hide()
        self._result_frame.show()

    def _reset(self):
        self._timer_lbl.setStyleSheet(
            f"font-size:32px;font-weight:bold;color:{PALETTE['primary']};"
        )
        self._result_frame.hide()
        self._start_btn.show()
