"""
首次运行引导向导（3步）
Step 1 → 欢迎 + 功能介绍
Step 2 → 创建第一个学生档案
Step 3 → 配置 API Key
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QStackedWidget, QWidget, QFrame,
    QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import config
from data import database as db
from core.knowledge_map import GRADES
from ui.styles import PALETTE


FEATURE_ITEMS = [
    ("📝", "AI 智能出题", "根据年级知识点自动生成高质量试卷"),
    ("📷", "拍照批改",   "拍下手写答案，自动识别和批改"),
    ("📊", "深度分析",   "知识点掌握情况数据化精准诊断"),
    ("🎯", "专项练习",   "针对薄弱知识点生成专项练习题"),
    ("🔊", "语音讲解",   "AI 生成口语化讲解，Edge TTS 朗读"),
]


class StepIndicator(QWidget):
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.total = total
        self._current = 0
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        self._dots: list[QLabel] = []
        for i in range(total):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            layout.addWidget(dot)
            self._dots.append(dot)
        self._refresh()

    def set_step(self, step: int):
        self._current = step
        self._refresh()

    def _refresh(self):
        for i, dot in enumerate(self._dots):
            if i == self._current:
                dot.setStyleSheet(
                    f"background:{PALETTE['primary']};border-radius:5px;"
                )
            elif i < self._current:
                dot.setStyleSheet(
                    f"background:{PALETTE['success']};border-radius:5px;"
                )
            else:
                dot.setStyleSheet(
                    f"background:{PALETTE['border']};border-radius:5px;"
                )


class OnboardingDialog(QDialog):
    completed = pyqtSignal(int)  # student_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用")
        self.setFixedSize(560, 460)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self._student_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 顶部色带
        header_bar = QFrame()
        header_bar.setFixedHeight(6)
        header_bar.setStyleSheet(f"background: {PALETTE['primary']};")
        outer.addWidget(header_bar)

        main = QVBoxLayout()
        main.setContentsMargins(36, 28, 36, 24)
        main.setSpacing(20)
        outer.addLayout(main)

        # 步骤指示器
        self._indicator = StepIndicator(3)
        main.addWidget(self._indicator, alignment=Qt.AlignmentFlag.AlignCenter)

        # 页面堆栈
        self._stack = QStackedWidget()
        main.addWidget(self._stack, 1)
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_student())
        self._stack.addWidget(self._page_api())

        # 底部按钮
        btn_row = QHBoxLayout()
        self._back_btn = QPushButton("← 上一步")
        self._back_btn.setObjectName("btn_secondary")
        self._back_btn.setFixedHeight(40)
        self._back_btn.hide()
        self._back_btn.clicked.connect(self._go_back)
        btn_row.addWidget(self._back_btn)
        btn_row.addStretch()

        self._next_btn = QPushButton("开始使用  →")
        self._next_btn.setObjectName("btn_primary")
        self._next_btn.setFixedHeight(40)
        self._next_btn.setFixedWidth(140)
        self._next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self._next_btn)
        main.addLayout(btn_row)

        self._step = 0

    def _page_welcome(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("欢迎使用小学数学智能练习系统")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {PALETTE['text_primary']};"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        sub = QLabel("基于 DeepSeek AI + 人教版知识体系，帮助孩子精准突破薄弱知识点")
        sub.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']};")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        for icon, name, desc in FEATURE_ITEMS:
            row = QFrame()
            row.setStyleSheet(
                f"background:{PALETTE['bg']}; border-radius:8px; padding: 2px;"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.setSpacing(12)
            ic = QLabel(icon)
            ic.setStyleSheet("font-size: 20px; background:transparent;")
            ic.setFixedWidth(28)
            rl.addWidget(ic)
            text_col = QVBoxLayout()
            n = QLabel(name)
            n.setStyleSheet(f"font-weight:bold; font-size:13px; background:transparent; color:{PALETTE['text_primary']};")
            text_col.addWidget(n)
            d = QLabel(desc)
            d.setStyleSheet(f"font-size:11px; color:{PALETTE['text_secondary']}; background:transparent;")
            text_col.addWidget(d)
            rl.addLayout(text_col, 1)
            layout.addWidget(row)

        layout.addStretch()
        return w

    def _page_student(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("创建第一个学生档案")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {PALETTE['text_primary']};")
        layout.addWidget(title)
        hint = QLabel("每个学生有独立的练习记录、知识点掌握度和分析报告")
        hint.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']};")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(8)

        # 姓名
        name_lbl = QLabel("孩子的姓名")
        name_lbl.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']};")
        layout.addWidget(name_lbl)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例：小明")
        self._name_edit.setFixedHeight(42)
        self._name_edit.setStyleSheet(f"font-size: 14px;")
        layout.addWidget(self._name_edit)

        # 年级
        grade_lbl = QLabel("当前年级")
        grade_lbl.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']};")
        layout.addWidget(grade_lbl)
        self._grade_combo = QComboBox()
        self._grade_combo.addItems(GRADES)
        self._grade_combo.setCurrentText("三年级")
        self._grade_combo.setFixedHeight(42)
        self._grade_combo.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._grade_combo)

        self._student_err = QLabel("")
        self._student_err.setStyleSheet(f"color: {PALETTE['danger']}; font-size: 12px;")
        layout.addWidget(self._student_err)
        layout.addStretch()
        return w

    def _page_api(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("配置 DeepSeek API Key")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {PALETTE['text_primary']};")
        layout.addWidget(title)

        # 说明卡片
        info_card = QFrame()
        info_card.setStyleSheet(
            f"background:{PALETTE['primary_light']}; border-radius:8px; border: 1px solid {PALETTE['primary']}33;"
        )
        il = QVBoxLayout(info_card)
        il.setContentsMargins(14, 10, 14, 10)
        il.setSpacing(4)
        for line in [
            "💡 API Key 用于 AI 出题、批改和分析功能",
            "🔒 Key 仅保存在本机，不会上传到任何服务器",
            "🔑 可前往 platform.deepseek.com 免费注册获取",
        ]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE['primary']}; background:transparent;")
            il.addWidget(lbl)
        layout.addWidget(info_card)

        key_lbl = QLabel("API Key")
        key_lbl.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']};")
        layout.addWidget(key_lbl)
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxx")
        self._key_edit.setFixedHeight(42)
        existing = config.get("api_key") or ""
        self._key_edit.setText(existing)
        layout.addWidget(self._key_edit)

        test_btn = QPushButton("🔗  验证 API Key")
        test_btn.setObjectName("btn_secondary")
        test_btn.setFixedHeight(36)
        test_btn.clicked.connect(self._test_key)
        layout.addWidget(test_btn)

        self._api_status = QLabel("可跳过，稍后在设置中配置" if not existing else "")
        self._api_status.setStyleSheet(f"font-size: 12px; color: {PALETTE['text_hint']};")
        layout.addWidget(self._api_status)
        layout.addStretch()

        ready_lbl = QLabel("🎉  完成配置后即可开始练习！")
        ready_lbl.setStyleSheet(f"font-size: 13px; color: {PALETTE['success']}; font-weight: bold;")
        layout.addWidget(ready_lbl)
        return w

    def _test_key(self):
        key = self._key_edit.text().strip()
        if not key:
            self._api_status.setStyleSheet(f"font-size: 12px; color: {PALETTE['danger']};")
            self._api_status.setText("请先输入 API Key")
            return
        self._api_status.setStyleSheet(f"font-size: 12px; color: {PALETTE['text_hint']};")
        self._api_status.setText("验证中...")
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=key,
                base_url=config.get("api_base_url") or "https://api.deepseek.com",
            )
            client.chat.completions.create(
                model=config.get("model_chat") or "deepseek-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            self._api_status.setStyleSheet(f"font-size: 12px; color: {PALETTE['success']};")
            self._api_status.setText("✓ 验证成功！API 可正常使用")
        except Exception as e:
            self._api_status.setStyleSheet(f"font-size: 12px; color: {PALETTE['danger']};")
            self._api_status.setText(f"✗ 验证失败：{str(e)[:60]}")

    def _go_next(self):
        if self._step == 0:
            self._step = 1
            self._stack.setCurrentIndex(1)
            self._indicator.set_step(1)
            self._back_btn.show()
            self._next_btn.setText("下一步  →")

        elif self._step == 1:
            name = self._name_edit.text().strip()
            if not name:
                self._student_err.setText("请输入孩子的姓名")
                return
            self._student_err.setText("")
            grade = self._grade_combo.currentText()
            sid = db.create_student(name, grade)
            config.set_value("default_student_id", sid)
            config.set_value("default_grade", grade)
            self._student_id = sid
            self._step = 2
            self._stack.setCurrentIndex(2)
            self._indicator.set_step(2)
            self._next_btn.setText("完成，开始使用 ✓")

        elif self._step == 2:
            key = self._key_edit.text().strip()
            if key:
                config.set_value("api_key", key)
            self.completed.emit(self._student_id or 1)
            self.accept()

    def _go_back(self):
        if self._step > 0:
            self._step -= 1
            self._stack.setCurrentIndex(self._step)
            self._indicator.set_step(self._step)
            if self._step == 0:
                self._back_btn.hide()
                self._next_btn.setText("开始使用  →")
            elif self._step == 1:
                self._next_btn.setText("下一步  →")


def should_onboard() -> bool:
    """首次运行时返回 True"""
    students = db.get_all_students()
    return len(students) == 0


def run_onboarding(parent=None) -> bool:
    """运行引导，返回是否完成"""
    dlg = OnboardingDialog(parent)
    return dlg.exec() == QDialog.DialogCode.Accepted
