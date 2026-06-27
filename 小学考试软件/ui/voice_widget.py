"""
通用语音讲解组件
使用方式：在任何页面插入 VoiceButton 或 VoicePanel
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QComboBox, QSlider, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

import config
from core import tts_engine, ai_engine
from ui.styles import PALETTE


class TextGenWorker(QThread):
    """后台生成讲解文本"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, question: dict = None, knowledge_point: str = None, grade: str = ""):
        super().__init__()
        self.question = question
        self.knowledge_point = knowledge_point
        self.grade = grade

    def run(self):
        try:
            if self.question:
                text = ai_engine.generate_voice_explanation(self.question, self.grade)
            elif self.knowledge_point:
                text = ai_engine.generate_voice_kp_explanation(self.knowledge_point, self.grade)
            else:
                text = ""
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


class VoiceButton(QPushButton):
    """
    单个题目旁边的小喇叭按钮
    点击 → 生成讲解 → 朗读
    """
    _idle_signal = pyqtSignal()   # 用信号将子线程回调转回主线程

    def __init__(self, question: dict, grade: str = "", parent=None):
        super().__init__("🔊", parent)
        self.question = question
        self.grade = grade
        self._cached_text: str = ""
        self._worker: TextGenWorker | None = None
        self._is_playing = False
        self._idle_signal.connect(self._set_idle)

        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("语音讲解此题")
        self.setStyleSheet(
            f"QPushButton {{ background: {PALETTE['primary_light']}; color: {PALETTE['primary']}; "
            f"border: 1px solid {PALETTE['primary']}44; border-radius: 18px; font-size: 16px; }}"
            f"QPushButton:hover {{ background: {PALETTE['primary']}22; }}"
            f"QPushButton:disabled {{ color: {PALETTE['text_hint']}; background: {PALETTE['bg']}; }}"
        )
        self.clicked.connect(self._on_click)

    def _on_click(self):
        if self._is_playing:
            tts_engine.stop()
            self._set_idle()
            return

        voice = config.get("tts_voice") or tts_engine.DEFAULT_VOICE
        rate = config.get("tts_rate") or "-10%"

        if self._cached_text:
            self._play(self._cached_text, voice, rate)
            return

        # 生成讲解文本
        self.setEnabled(False)
        self.setText("⏳")

        self._worker = TextGenWorker(question=self.question, grade=self.grade)
        self._worker.finished.connect(lambda t: self._on_text_ready(t, voice, rate))
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_text_ready(self, text: str, voice: str, rate: str):
        self._cached_text = text
        self.setEnabled(True)
        self._play(text, voice, rate)

    def _play(self, text: str, voice: str, rate: str):
        self._is_playing = True
        self.setText("⏹")
        self.setToolTip("点击停止")
        tts_engine.speak(
            text, voice=voice, rate=rate,
            on_finish=lambda: self._idle_signal.emit(),
            on_error=lambda e: self._idle_signal.emit(),
        )

    def _set_idle(self):
        self._is_playing = False
        self.setText("🔊")
        self.setToolTip("语音讲解此题")

    def _on_error(self, err: str):
        self.setEnabled(True)
        self._set_idle()
        self.setToolTip(f"生成失败: {err[:30]}")


class KPVoiceButton(QPushButton):
    """知识点语音讲解按钮（用于分析报告页）"""
    _idle_signal = pyqtSignal()

    def __init__(self, knowledge_point: str, grade: str = "", parent=None):
        super().__init__("🔊 听讲解", parent)
        self.knowledge_point = knowledge_point
        self.grade = grade
        self._cached_text: str = ""
        self._worker: TextGenWorker | None = None
        self._is_playing = False
        self._idle_signal.connect(self._set_idle)

        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton {{ background: {PALETTE['primary_light']}; color: {PALETTE['primary']}; "
            f"border: none; border-radius: 6px; padding: 2px 10px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {PALETTE['primary']}22; }}"
        )
        self.clicked.connect(self._on_click)

    def _on_click(self):
        if self._is_playing:
            tts_engine.stop()
            self._set_idle()
            return

        voice = config.get("tts_voice") or tts_engine.DEFAULT_VOICE
        rate = config.get("tts_rate") or "-10%"

        if self._cached_text:
            self._play(self._cached_text, voice, rate)
            return

        self.setEnabled(False)
        self.setText("⏳ 生成中...")

        self._worker = TextGenWorker(
            knowledge_point=self.knowledge_point, grade=self.grade
        )
        self._worker.finished.connect(lambda t: self._on_text_ready(t, voice, rate))
        self._worker.error.connect(lambda e: (self.setEnabled(True), self._set_idle()))
        self._worker.start()

    def _on_text_ready(self, text: str, voice: str, rate: str):
        self._cached_text = text
        self.setEnabled(True)
        self._play(text, voice, rate)

    def _play(self, text: str, voice: str, rate: str):
        self._is_playing = True
        self.setText("⏹ 停止")
        tts_engine.speak(
            text, voice=voice, rate=rate,
            on_finish=lambda: self._idle_signal.emit(),
            on_error=lambda e: self._idle_signal.emit(),
        )

    def _set_idle(self):
        self._is_playing = False
        self.setText("🔊 听讲解")


class VoiceControlBar(QFrame):
    """
    全局语音控制栏（放在页面顶部或底部）
    提供：声音选择 / 语速调节 / 停止按钮
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PALETTE['card']}; border-radius: 10px; "
            f"border: 1px solid {PALETTE['border']}; }}"
        )
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # 声音图标
        icon = QLabel("🔊")
        icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon)

        layout.addWidget(QLabel("语音："))
        self._voice_combo = QComboBox()
        self._voice_combo.setFixedWidth(160)
        for name in tts_engine.VOICES:
            self._voice_combo.addItem(name)
        saved_voice = config.get("tts_voice") or tts_engine.DEFAULT_VOICE
        for i, v in enumerate(tts_engine.VOICES.values()):
            if v == saved_voice:
                self._voice_combo.setCurrentIndex(i)
                break
        self._voice_combo.currentIndexChanged.connect(self._save_voice)
        layout.addWidget(self._voice_combo)

        layout.addWidget(QLabel("语速："))
        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setFixedWidth(100)
        self._rate_slider.setRange(-30, 30)
        # 从config读取，默认-10（稍慢）
        saved_rate_str = config.get("tts_rate") or "-10%"
        saved_rate = int(saved_rate_str.replace("%", ""))
        self._rate_slider.setValue(saved_rate)
        self._rate_label = QLabel(f"{saved_rate:+d}%")
        self._rate_label.setFixedWidth(36)
        self._rate_label.setStyleSheet(f"font-size: 12px; color: {PALETTE['text_secondary']};")
        self._rate_slider.valueChanged.connect(self._on_rate_changed)
        layout.addWidget(self._rate_slider)
        layout.addWidget(self._rate_label)

        layout.addStretch()

        self._stop_btn = QPushButton("⏹ 停止朗读")
        self._stop_btn.setObjectName("btn_secondary")
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.clicked.connect(tts_engine.stop)
        layout.addWidget(self._stop_btn)

    def _save_voice(self):
        name = self._voice_combo.currentText()
        voice = tts_engine.VOICES.get(name, tts_engine.DEFAULT_VOICE)
        config.set_value("tts_voice", voice)

    def _on_rate_changed(self, val: int):
        self._rate_label.setText(f"{val:+d}%")
        config.set_value("tts_rate", f"{val:+d}%")

    def get_voice(self) -> str:
        name = self._voice_combo.currentText()
        return tts_engine.VOICES.get(name, tts_engine.DEFAULT_VOICE)

    def get_rate(self) -> str:
        return f"{self._rate_slider.value():+d}%"
