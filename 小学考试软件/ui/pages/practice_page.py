from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QProgressBar, QLineEdit,
    QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

import config
from data import database as db
from core import ai_engine
from ui.styles import PALETTE
from ui.voice_widget import VoiceButton, VoiceControlBar


class PracticeWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, kp: str, grade: str, count: int = 6):
        super().__init__()
        self.kp = kp
        self.grade = grade
        self.count = count

    def run(self):
        try:
            result = ai_engine.generate_practice(self.kp, self.grade, self.count)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class GuideWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, question: dict, grade: str, history: list):
        super().__init__()
        self.question = question
        self.grade = grade
        self.history = history

    def run(self):
        try:
            reply = ai_engine.guide_student(self.question, self.grade, self.history)
            self.finished.emit(reply)
        except Exception as e:
            self.error.emit(str(e))


class GuideDialog(QDialog):
    """AI引导对话弹窗"""

    def __init__(self, question: dict, grade: str, parent=None):
        super().__init__(parent)
        self.question = question
        self.grade = grade
        self._history: list[dict] = []
        self._worker: GuideWorker | None = None
        self.setWindowTitle("AI 辅导助手")
        self.setMinimumSize(480, 440)
        self._build_ui()
        self._send_initial()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(f"📖 {self.question.get('content', '')[:60]}")
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size:13px;color:{PALETTE['text_secondary']};")
        layout.addWidget(title)

        self._chat_area = QTextEdit()
        self._chat_area.setReadOnly(True)
        self._chat_area.setStyleSheet(
            f"background:{PALETTE['bg']};border:1px solid {PALETTE['border']};"
            f"border-radius:8px;font-size:13px;padding:8px;"
        )
        layout.addWidget(self._chat_area, 1)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入你的想法或提问...")
        self._input.setFixedHeight(36)
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("发送")
        self._send_btn.setObjectName("btn_primary")
        self._send_btn.setFixedHeight(36)
        self._send_btn.setFixedWidth(64)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)
        layout.addLayout(input_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"font-size:11px;color:{PALETTE['text_hint']};")
        layout.addWidget(self._status_lbl)

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("btn_secondary")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _append_msg(self, role: str, text: str):
        color = PALETTE["primary"] if role == "assistant" else PALETTE["text_primary"]
        name = "老师" if role == "assistant" else "我"
        self._chat_area.append(
            f'<p><b style="color:{color};">{name}：</b>{text}</p>'
        )

    def _send_initial(self):
        self._status_lbl.setText("老师正在思考...")
        self._send_btn.setEnabled(False)
        self._worker = GuideWorker(self.question, self.grade, [])
        self._worker.finished.connect(self._on_reply)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_send(self):
        text = self._input.text().strip()
        if not text or (self._worker and self._worker.isRunning()):
            return
        self._input.clear()
        self._history.append({"role": "user", "content": text})
        self._append_msg("user", text)
        self._send_btn.setEnabled(False)
        self._status_lbl.setText("老师正在思考...")
        self._worker = GuideWorker(self.question, self.grade, self._history.copy())
        self._worker.finished.connect(self._on_reply)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(str)
    def _on_reply(self, text: str):
        self._history.append({"role": "assistant", "content": text})
        self._append_msg("assistant", text)
        self._send_btn.setEnabled(True)
        self._status_lbl.setText("")
        self._input.setFocus()

    @pyqtSlot(str)
    def _on_error(self, err: str):
        self._status_lbl.setText(f"出错了：{err[:60]}")
        self._send_btn.setEnabled(True)


class QuestionCard(QFrame):
    def __init__(self, question: dict, index: int, grade: str = ""):
        super().__init__()
        self.question = question
        self._grade = grade
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PALETTE['card']}; border-radius: 10px; "
            f"border: 1px solid {PALETTE['border']}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # 题头
        header = QHBoxLayout()
        num_lbl = QLabel(f"第{index}题")
        num_lbl.setStyleSheet(f"font-weight: bold; color: {PALETTE['primary']}; font-size: 14px;")
        header.addWidget(num_lbl)

        diff_color = {
            "简单": PALETTE["success"],
            "中等": PALETTE["primary"],
            "困难": PALETTE["danger"],
        }.get(question.get("difficulty", "中等"), PALETTE["primary"])
        diff_lbl = QLabel(question.get("difficulty", ""))
        diff_lbl.setStyleSheet(
            f"background: {diff_color}22; color: {diff_color}; border-radius: 4px; "
            f"padding: 2px 8px; font-size: 11px; font-weight: bold;"
        )
        header.addWidget(diff_lbl)
        header.addSpacing(8)

        type_lbl = QLabel(question.get("type", ""))
        type_lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE['text_hint']};")
        header.addWidget(type_lbl)
        header.addStretch()

        score_lbl = QLabel(f"{question.get('score', 0)}分")
        score_lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE['text_secondary']};")
        header.addWidget(score_lbl)

        # 语音讲解按钮
        self._voice_btn = VoiceButton(question, grade=self._grade)
        header.addWidget(self._voice_btn)

        # 动图讲解按钮
        anim_btn = QPushButton("🎬 动图讲解")
        anim_btn.setFixedHeight(30)
        anim_btn.setStyleSheet(
            f"QPushButton{{background:{PALETTE['warning_light']};color:{PALETTE['warning']};"
            f"border:none;border-radius:6px;padding:2px 10px;font-size:12px;}}"
        )
        anim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        anim_btn.clicked.connect(self._open_anim_explain)
        header.addWidget(anim_btn)

        # AI辅导按钮
        guide_btn = QPushButton("💬 AI辅导")
        guide_btn.setFixedHeight(30)
        guide_btn.setStyleSheet(
            f"QPushButton{{background:{PALETTE['success_light']};color:{PALETTE['success']};"
            f"border:none;border-radius:6px;padding:2px 10px;font-size:12px;}}"
        )
        guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        guide_btn.clicked.connect(self._open_guide)
        header.addWidget(guide_btn)
        layout.addLayout(header)

        # 题目内容
        content_lbl = QLabel(question.get("content", ""))
        content_lbl.setWordWrap(True)
        content_lbl.setStyleSheet("font-size: 14px; line-height: 1.6;")
        layout.addWidget(content_lbl)

        # 选项
        if question.get("options"):
            for opt in question["options"]:
                opt_lbl = QLabel(opt)
                opt_lbl.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']}; padding-left: 12px;")
                layout.addWidget(opt_lbl)

        # 答题框
        ans_row = QHBoxLayout()
        ans_lbl = QLabel("我的答案：")
        ans_lbl.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']};")
        ans_row.addWidget(ans_lbl)
        self._ans_edit = QLineEdit()
        self._ans_edit.setPlaceholderText("填写答案...")
        self._ans_edit.setFixedHeight(34)
        ans_row.addWidget(self._ans_edit, 1)
        layout.addLayout(ans_row)

        # 解析（折叠）
        self._answer_frame = QFrame()
        self._answer_frame.hide()
        af_layout = QVBoxLayout(self._answer_frame)
        af_layout.setContentsMargins(12, 10, 12, 10)
        af_layout.setSpacing(6)
        self._answer_frame.setStyleSheet(
            f"background: {PALETTE['primary_light']}; border-radius: 8px;"
        )

        correct_lbl = QLabel(f"✓ 正确答案：{question.get('answer', '')}")
        correct_lbl.setStyleSheet(f"font-weight: bold; color: {PALETTE['primary']}; font-size: 13px;")
        af_layout.addWidget(correct_lbl)

        if question.get("answer_detail"):
            detail_lbl = QLabel(f"解题过程：{question['answer_detail']}")
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE['text_secondary']};")
            af_layout.addWidget(detail_lbl)

        if question.get("error_traps"):
            trap_lbl = QLabel(f"⚠ 易错点：{question['error_traps']}")
            trap_lbl.setWordWrap(True)
            trap_lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE['warning']};")
            af_layout.addWidget(trap_lbl)

        layout.addWidget(self._answer_frame)

        # 查看解析按钮
        self._reveal_btn = QPushButton("查看答案与解析 ▼")
        self._reveal_btn.setObjectName("btn_secondary")
        self._reveal_btn.setFixedHeight(32)
        self._reveal_btn.clicked.connect(self._toggle_answer)
        layout.addWidget(self._reveal_btn)

    def _toggle_answer(self):
        if self._answer_frame.isHidden():
            self._answer_frame.show()
            self._reveal_btn.setText("收起解析 ▲")
        else:
            self._answer_frame.hide()
            self._reveal_btn.setText("查看答案与解析 ▼")

    def _open_guide(self):
        if not config.get("api_key"):
            QMessageBox.warning(self.window(), "API未配置", "请先在【设置】中填写 DeepSeek API Key")
            return
        dlg = GuideDialog(self.question, self._grade, self.window())
        dlg.exec()

    def _open_anim_explain(self):
        if not config.get("api_key"):
            QMessageBox.warning(self.window(), "API未配置", "请先在【设置】中填写 DeepSeek API Key")
            return
        from ui.widgets.anim_explain_dialog import AnimExplainDialog
        dlg = AnimExplainDialog(self.question, self._grade, self.window())
        dlg.exec()

    def get_answer(self) -> str:
        return self._ans_edit.text().strip()


class PracticePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._questions: list = []
        self._q_cards: list[QuestionCard] = []
        self._current_kp: str = ""
        self._current_grade: str = "三年级"
        self._worker: PracticeWorker | None = None
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(20)

        # 页头
        header = QHBoxLayout()
        title = QLabel("专项练习")
        title.setObjectName("label_title")
        header.addWidget(title)
        header.addStretch()
        self._kp_badge = QLabel("")
        self._kp_badge.setStyleSheet(
            f"background: {PALETTE['primary_light']}; color: {PALETTE['primary']}; "
            f"border-radius: 6px; padding: 4px 12px; font-weight: bold; font-size: 13px;"
        )
        header.addWidget(self._kp_badge)
        main_layout.addLayout(header)

        # 语音控制栏
        self._voice_bar = VoiceControlBar()
        main_layout.addWidget(self._voice_bar)

        # 顶部：知识点选择 + 出题控制
        ctrl_card = QFrame()
        ctrl_card.setObjectName("card")
        ctrl_card.setStyleSheet(
            f"QFrame#card {{ background: {PALETTE['card']}; border-radius: 10px; "
            f"border: 1px solid {PALETTE['border']}; }}"
        )
        ctrl_layout = QHBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(20, 16, 20, 16)
        ctrl_layout.setSpacing(16)

        kp_lbl = QLabel("知识点：")
        kp_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']};")
        ctrl_layout.addWidget(kp_lbl)

        self._kp_input = QLineEdit()
        self._kp_input.setPlaceholderText("输入或从报告页点击专练...")
        self._kp_input.setFixedHeight(36)
        ctrl_layout.addWidget(self._kp_input, 1)

        self._gen_btn = QPushButton("✨  生成专项题")
        self._gen_btn.setObjectName("btn_primary")
        self._gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_btn.clicked.connect(self._on_generate)
        ctrl_layout.addWidget(self._gen_btn)
        main_layout.addWidget(ctrl_card)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.hide()
        main_layout.addWidget(self._progress)

        # 题目滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._q_container = QWidget()
        self._q_layout = QVBoxLayout(self._q_container)
        self._q_layout.setContentsMargins(0, 0, 8, 0)
        self._q_layout.setSpacing(12)
        scroll.setWidget(self._q_container)
        main_layout.addWidget(scroll, 1)

        # 空状态
        self._empty_lbl = QLabel("从薄弱知识点出发，生成专项练习题\n系统会根据你的错误记录推荐知识点")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {PALETTE['text_hint']}; font-size: 14px; margin: 40px;")
        self._q_layout.addWidget(self._empty_lbl)
        self._q_layout.addStretch()

        # 底部：薄弱知识点快捷列表 + 提交批改
        bottom_card = QFrame()
        bottom_card.setObjectName("card")
        bottom_card.setStyleSheet(
            f"QFrame#card {{ background: {PALETTE['card']}; border-radius: 10px; "
            f"border: 1px solid {PALETTE['border']}; }}"
        )
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(16, 12, 16, 12)
        bottom_layout.setSpacing(8)

        bottom_top_row = QHBoxLayout()
        quick_lbl = QLabel("📌  薄弱知识点快捷练习")
        quick_lbl.setStyleSheet(f"font-weight: bold; color: {PALETTE['text_secondary']}; font-size: 12px;")
        bottom_top_row.addWidget(quick_lbl)
        bottom_top_row.addStretch()

        self._submit_btn = QPushButton("✅  提交批改")
        self._submit_btn.setObjectName("btn_primary")
        self._submit_btn.setFixedHeight(34)
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.clicked.connect(self._on_submit_answers)
        self._submit_btn.hide()
        bottom_top_row.addWidget(self._submit_btn)
        bottom_layout.addLayout(bottom_top_row)

        self._weak_btns_row = QHBoxLayout()
        self._weak_btns_row.setSpacing(8)
        bottom_layout.addLayout(self._weak_btns_row)
        main_layout.addWidget(bottom_card)

        self._refresh_weak_buttons()

    def start_practice(self, knowledge_point: str):
        self._kp_input.setText(knowledge_point)
        self._on_generate()

    def load_retry_questions(self, questions: list, grade: str = ""):
        """由错题本调用：直接展示指定题目，跳过生成步骤。"""
        if grade:
            self._current_grade = grade
        self._questions = questions
        self._q_cards = []
        if questions:
            self._current_kp = questions[0].get("knowledge_point", "专项练习")
        self._kp_badge.setText(f"📍 {self._current_kp}")
        self._clear_questions()
        for i, q in enumerate(questions, 1):
            card = QuestionCard(q, i, grade=self._current_grade)
            self._q_layout.addWidget(card)
            self._q_cards.append(card)
        self._q_layout.addStretch()
        self._submit_btn.show()

    def _on_generate(self):
        kp = self._kp_input.text().strip()
        if not kp:
            QMessageBox.warning(self, "提示", "请输入知识点名称")
            return
        if not config.get("api_key"):
            QMessageBox.warning(self, "API未配置", "请先在【设置】中填写 DeepSeek API Key")
            return

        sid = config.get("default_student_id")
        grade = "三年级"
        if sid:
            student = db.get_student(int(sid))
            if student:
                grade = student["grade"]

        self._current_kp = kp
        self._current_grade = grade
        self._kp_badge.setText(f"📍 {kp}")
        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("生成中...")
        self._progress.show()
        self._clear_questions()

        self._worker = PracticeWorker(kp, grade, count=6)
        self._worker.finished.connect(self._on_generated)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(dict)
    def _on_generated(self, data: dict):
        self._progress.hide()
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("✨  生成专项题")

        self._clear_questions()
        questions = data.get("questions", [])
        self._questions = questions
        self._q_cards = []

        if not questions:
            self._q_layout.addWidget(self._empty_lbl)
            self._submit_btn.hide()
            return

        for i, q in enumerate(questions, 1):
            card = QuestionCard(q, i, grade=self._current_grade)
            self._q_layout.addWidget(card)
            self._q_cards.append(card)

        self._q_layout.addStretch()
        self._submit_btn.show()

    def _on_submit_answers(self):
        if not self._q_cards:
            return
        sid = config.get("default_student_id")
        if not sid:
            QMessageBox.warning(self, "提示", "请先在【设置】中选择学生")
            return
        student_id = int(sid)

        # 自我批改：对比标准答案
        correct = 0
        results = []
        for card in self._q_cards:
            q = card.question
            student_ans = card.get_answer()
            std_ans = str(q.get("answer", "")).strip()
            is_correct = student_ans != "" and student_ans == std_ans
            if is_correct:
                correct += 1
            results.append({
                "question": q.get("content", ""),
                "kp": q.get("knowledge_point", self._current_kp),
                "student_answer": student_ans,
                "correct_answer": std_ans,
                "is_correct": is_correct,
            })

        total = len(results)
        pct = round(correct / total * 100) if total else 0

        # 更新kp_mastery
        kp_delta: dict[str, dict] = {}
        for r in results:
            kp = r["kp"]
            if kp not in kp_delta:
                kp_delta[kp] = {"correct": 0, "total": 0}
            kp_delta[kp]["total"] += 1
            if r["is_correct"]:
                kp_delta[kp]["correct"] += 1
        grade = self._current_grade
        for kp, v in kp_delta.items():
            kp_stats = {kp: {"correct": v["correct"], "total": v["total"],
                             "rate": v["correct"] / v["total"] if v["total"] else 0}}
            db.update_kp_mastery(student_id, grade, kp_stats)

        # 积分 + 打卡
        pts = correct
        db.award_points(student_id, pts, "专练自批")
        db.checkin_today(student_id, total)
        newly = db.check_and_award_badges(student_id)

        msg = f"完成 {total} 题，答对 {correct} 题（{pct}%）\n获得 {pts} 积分"
        if newly:
            icon, name, _ = db.BADGE_DEFS.get(newly[0], ("🏅", newly[0], ""))
            msg += f"\n\n{icon} 新成就解锁：{name}！"
        QMessageBox.information(self, "批改完成", msg)
        self._submit_btn.hide()

    @pyqtSlot(str)
    def _on_error(self, err: str):
        self._progress.hide()
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("✨  生成专项题")
        QMessageBox.critical(self, "生成失败", f"出题失败：\n{err}")

    def _clear_questions(self):
        while self._q_layout.count():
            item = self._q_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._empty_lbl:
                w.deleteLater()
        self._q_cards.clear()

    def _refresh_weak_buttons(self):
        while self._weak_btns_row.count():
            item = self._weak_btns_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sid = config.get("default_student_id")
        if not sid:
            return

        kp_list = db.get_kp_mastery(int(sid))
        weak = [k for k in kp_list if k["rate"] < 0.6][:6]
        for kp in weak:
            btn = QPushButton(kp["knowledge_point"][:8])
            btn.setStyleSheet(
                f"background: {PALETTE['danger_light']}; color: {PALETTE['danger']}; "
                f"border: 1px solid {PALETTE['danger']}33; border-radius: 6px; "
                f"padding: 4px 10px; font-size: 12px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{kp['knowledge_point']}  正确率{round(kp['rate']*100)}%")
            btn.clicked.connect(lambda _, k=kp["knowledge_point"]: self.start_practice(k))
            self._weak_btns_row.addWidget(btn)
        self._weak_btns_row.addStretch()

    def on_activate(self):
        self._refresh_weak_buttons()
