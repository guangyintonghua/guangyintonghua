from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QFrame, QSizePolicy, QMessageBox, QProgressBar
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, pyqtSlot, QTimer,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QRect
)
from PyQt6.QtGui import QColor

import config
from core import ai_engine
from ui.styles import PALETTE

# Per-step accent color pairs: (border/badge, light background)
_STEP_COLORS = [
    ("#4B7BEC", "#EBF0FF"),
    ("#52B788", "#E8F5EF"),
    ("#FD9644", "#FEF3E8"),
    ("#FC5C65", "#FDEDED"),
    ("#2BCBBA", "#E4F9F8"),
    ("#8854D0", "#F0EBFF"),
]


class StepsWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, question: dict, grade: str):
        super().__init__()
        self.question = question
        self.grade = grade

    def run(self):
        try:
            result = ai_engine.get_solution_steps(self.question, self.grade)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class StepCard(QFrame):
    """Single step card with typewriter content reveal."""
    typewriter_done = pyqtSignal()

    def __init__(self, step: dict, step_num: int, total: int, parent=None):
        super().__init__(parent)
        self._full_content = step.get("content", "")
        self._key_point = step.get("key_point", "")
        self._type_index = 0
        self._type_timer = QTimer(self)
        self._type_timer.timeout.connect(self._type_next_char)

        accent, bg_light = _STEP_COLORS[(step_num - 1) % len(_STEP_COLORS)]
        self.setObjectName("step_card")
        self.setStyleSheet(
            f"QFrame#step_card {{"
            f"  background: {PALETTE['card']};"
            f"  border: 1px solid {PALETTE['border']};"
            f"  border-left: 5px solid {accent};"
            f"  border-radius: 12px;"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Step header row
        hdr = QHBoxLayout()
        badge = QLabel(str(step_num))
        badge.setFixedSize(32, 32)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {accent}; color: white; border-radius: 16px;"
            f"font-size: 15px; font-weight: bold; border: none;"
        )
        hdr.addWidget(badge)

        title_lbl = QLabel(step.get("title", ""))
        title_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {accent};"
            f"background: transparent; border: none;"
        )
        hdr.addWidget(title_lbl, 1)

        prog_lbl = QLabel(f"{step_num} / {total}")
        prog_lbl.setStyleSheet(
            f"font-size: 12px; color: {PALETTE['text_hint']};"
            f"background: transparent; border: none;"
        )
        hdr.addWidget(prog_lbl)
        layout.addLayout(hdr)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {PALETTE['divider']}; border: none;")
        layout.addWidget(line)

        # Content (typewriter target)
        self._content_lbl = QLabel()
        self._content_lbl.setWordWrap(True)
        self._content_lbl.setStyleSheet(
            f"font-size: 15px; color: {PALETTE['text_primary']};"
            f"line-height: 1.8; background: transparent; border: none;"
            f"min-height: 48px;"
        )
        layout.addWidget(self._content_lbl)

        # Key point chip (initially hidden)
        self._kp_frame = QFrame()
        self._kp_frame.setStyleSheet(
            f"background: {bg_light}; border-radius: 6px;"
            f"border: 1px solid {accent}40;"
        )
        kp_inner = QHBoxLayout(self._kp_frame)
        kp_inner.setContentsMargins(12, 6, 12, 6)
        self._kp_lbl = QLabel()
        self._kp_lbl.setStyleSheet(
            f"font-size: 13px; color: {accent}; font-weight: bold;"
            f"background: transparent; border: none;"
        )
        kp_inner.addWidget(self._kp_lbl)
        self._kp_frame.hide()
        layout.addWidget(self._kp_frame)

    def start_typewriter(self, speed_ms: int = 22):
        self._type_index = 0
        self._content_lbl.setText("")
        self._kp_frame.hide()
        self._type_timer.start(speed_ms)

    def finish_instantly(self):
        """Skip typewriter and show all content immediately."""
        self._type_timer.stop()
        self._content_lbl.setText(self._full_content)
        if self._key_point:
            self._kp_lbl.setText(f"💡  {self._key_point}")
            self._kp_frame.show()
        self.typewriter_done.emit()

    def _type_next_char(self):
        if self._type_index < len(self._full_content):
            self._type_index += 1
            self._content_lbl.setText(self._full_content[:self._type_index])
        else:
            self._type_timer.stop()
            if self._key_point:
                self._kp_lbl.setText(f"💡  {self._key_point}")
                self._kp_frame.show()
            self.typewriter_done.emit()


class _CardArea(QWidget):
    """Container for step cards; clips overflow for slide animation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)


class AnimExplainDialog(QDialog):
    """Step-by-step animated solution dialog."""

    def __init__(self, question: dict, grade: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("动图讲解")
        self.setMinimumSize(580, 480)
        self.resize(640, 520)
        self._question = question
        self._grade = grade
        self._steps: list[dict] = []
        self._current = 0
        self._playing = False
        self._worker: StepsWorker | None = None
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._next_step)
        self._current_card: StepCard | None = None
        self._slide_in: QPropertyAnimation | None = None
        self._slide_out: QPropertyAnimation | None = None
        self._slide_group: QParallelAnimationGroup | None = None
        self._build_ui()
        self._load_steps()

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        # Title + knowledge point chip
        hdr = QHBoxLayout()
        title_lbl = QLabel("动图讲解")
        title_lbl.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {PALETTE['text_primary']};"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        self._kp_chip = QLabel(self._question.get("knowledge_point", ""))
        self._kp_chip.setStyleSheet(
            f"background: {PALETTE['primary_light']}; color: {PALETTE['primary']};"
            f"border-radius: 4px; padding: 3px 10px; font-size: 12px; font-weight: bold;"
        )
        hdr.addWidget(self._kp_chip)
        outer.addLayout(hdr)

        # Question brief
        brief = self._question.get("content", "")
        if len(brief) > 60:
            brief = brief[:58] + "…"
        q_lbl = QLabel(brief)
        q_lbl.setWordWrap(True)
        q_lbl.setStyleSheet(
            f"font-size: 13px; color: {PALETTE['text_secondary']};"
            f"background: {PALETTE['bg']}; border-radius: 6px; padding: 8px 12px;"
        )
        outer.addWidget(q_lbl)

        # Progress dots
        self._dots_widget = QWidget()
        dots_layout = QHBoxLayout(self._dots_widget)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(8)
        dots_layout.addStretch()
        self._dots_layout = dots_layout
        outer.addWidget(self._dots_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Step card area (absolute positioning for slide animation)
        self._card_area = _CardArea()
        self._card_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._card_area.setMinimumHeight(200)
        outer.addWidget(self._card_area, 1)

        # Loading overlay (inside card area, shown until steps are ready)
        self._loading_widget = QWidget(self._card_area)
        ll = QVBoxLayout(self._loading_widget)
        ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_lbl = QLabel("AI 正在分析解题步骤，请稍候…")
        self._loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_lbl.setStyleSheet(
            f"font-size: 14px; color: {PALETTE['text_hint']};"
        )
        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setFixedHeight(4)
        self._loading_bar.setFixedWidth(240)
        ll.addWidget(self._loading_lbl)
        ll.addSpacing(8)
        ll.addWidget(self._loading_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self._prev_btn = QPushButton("◀  上一步")
        self._prev_btn.setObjectName("btn_secondary")
        self._prev_btn.setFixedHeight(36)
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._prev_step)
        ctrl.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶  自动播放")
        self._play_btn.setObjectName("btn_primary")
        self._play_btn.setFixedHeight(36)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)

        self._next_btn = QPushButton("下一步  ▶")
        self._next_btn.setObjectName("btn_secondary")
        self._next_btn.setFixedHeight(36)
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._next_step)
        ctrl.addWidget(self._next_btn)

        ctrl.addStretch()

        self._browser_btn = QPushButton("🌐  浏览器播放")
        self._browser_btn.setObjectName("btn_secondary")
        self._browser_btn.setFixedHeight(36)
        self._browser_btn.setEnabled(False)
        self._browser_btn.setToolTip("在默认浏览器中打开高质量动画讲解（无需额外安装）")
        self._browser_btn.clicked.connect(self._open_browser)
        ctrl.addWidget(self._browser_btn)

        outer.addLayout(ctrl)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep loading widget and current card filling the card area
        w = self._card_area.width()
        h = self._card_area.height()
        self._loading_widget.setGeometry(0, 0, w, h)
        if self._current_card:
            self._current_card.setGeometry(0, 0, w, h)

    # ── Step loading ───────────────────────────────────────────────────────

    def _load_steps(self):
        self._loading_widget.show()
        self._worker = StepsWorker(self._question, self._grade)
        self._worker.finished.connect(self._on_steps_ready)
        self._worker.error.connect(self._on_steps_error)
        self._worker.start()

    @pyqtSlot(dict)
    def _on_steps_ready(self, data: dict):
        self._steps = data.get("steps", [])
        self._loading_widget.hide()
        if not self._steps:
            self._loading_lbl.setText("未能生成解题步骤，请关闭后重试")
            self._loading_widget.show()
            return

        # Build progress dots
        for i in range(len(self._steps)):
            dot = QLabel("●" if i == 0 else "○")
            dot.setFixedSize(20, 20)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setObjectName(f"dot_{i}")
            self._dots_layout.insertWidget(i, dot)
        self._update_dots(0)

        self._current = 0
        self._show_step(0, animate=False)

        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(len(self._steps) > 1)
        self._play_btn.setEnabled(True)
        self._browser_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_steps_error(self, err: str):
        self._loading_bar.hide()
        self._loading_lbl.setText(f"生成失败：{err[:80]}")

    # ── Step display ───────────────────────────────────────────────────────

    def _show_step(self, index: int, animate: bool = True, direction: int = 1):
        """Show step[index]. direction: +1=forward, -1=backward."""
        if index < 0 or index >= len(self._steps):
            return

        w = self._card_area.width()
        h = self._card_area.height()

        new_card = StepCard(self._steps[index], index + 1, len(self._steps))
        new_card.setParent(self._card_area)
        new_card.typewriter_done.connect(self._on_typewriter_done)

        if animate and self._current_card:
            # Slide: new card comes in from right (or left if going backward)
            start_x = w * direction
            new_card.setGeometry(start_x, 0, w, h)
            new_card.show()

            old_card = self._current_card
            anim_in = QPropertyAnimation(new_card, b"geometry")
            anim_in.setDuration(320)
            anim_in.setStartValue(QRect(start_x, 0, w, h))
            anim_in.setEndValue(QRect(0, 0, w, h))
            anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

            anim_out = QPropertyAnimation(old_card, b"geometry")
            anim_out.setDuration(320)
            anim_out.setStartValue(QRect(0, 0, w, h))
            anim_out.setEndValue(QRect(-w * direction, 0, w, h))
            anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)

            self._slide_group = QParallelAnimationGroup()
            self._slide_group.addAnimation(anim_in)
            self._slide_group.addAnimation(anim_out)
            self._slide_group.finished.connect(old_card.deleteLater)
            self._slide_group.finished.connect(lambda: new_card.start_typewriter())
            self._slide_group.start()
        else:
            # No animation (first show, or instant skip)
            if self._current_card:
                self._current_card.deleteLater()
            new_card.setGeometry(0, 0, w, h)
            new_card.show()
            new_card.start_typewriter()

        self._current_card = new_card
        self._current = index
        self._update_dots(index)
        self._prev_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < len(self._steps) - 1)

    def _update_dots(self, active: int):
        for i in range(len(self._steps)):
            dot = self._dots_widget.findChild(QLabel, f"dot_{i}")
            if not dot:
                continue
            accent = _STEP_COLORS[i % len(_STEP_COLORS)][0]
            if i == active:
                dot.setText("●")
                dot.setStyleSheet(
                    f"font-size: 16px; color: {accent}; background: transparent;"
                )
            elif i < active:
                dot.setText("●")
                dot.setStyleSheet(
                    f"font-size: 12px; color: {PALETTE['text_hint']}; background: transparent;"
                )
            else:
                dot.setText("○")
                dot.setStyleSheet(
                    f"font-size: 14px; color: {PALETTE['text_hint']}; background: transparent;"
                )

    # ── Navigation ─────────────────────────────────────────────────────────

    def _next_step(self):
        if self._current_card:
            # If typewriter still running, finish instantly first
            if self._current_card._type_timer.isActive():
                self._current_card.finish_instantly()
                return
        if self._current < len(self._steps) - 1:
            self._show_step(self._current + 1, animate=True, direction=1)
        elif self._playing:
            self._stop_play()

    def _prev_step(self):
        if self._current_card and self._current_card._type_timer.isActive():
            self._current_card.finish_instantly()
            return
        if self._current > 0:
            self._show_step(self._current - 1, animate=True, direction=-1)

    def _on_typewriter_done(self):
        """Called when the current step's text is fully revealed."""
        if self._playing:
            # Auto-advance after a 2s pause
            self._auto_timer.start(2000)

    def _toggle_play(self):
        if self._playing:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        self._playing = True
        self._play_btn.setText("⏸  暂停")
        # If current step already fully shown, start timer now
        if self._current_card and not self._current_card._type_timer.isActive():
            self._auto_timer.start(2000)

    def _stop_play(self):
        self._playing = False
        self._auto_timer.stop()
        self._play_btn.setText("▶  自动播放")

    # ── Browser open ───────────────────────────────────────────────────────

    def _open_browser(self):
        if not self._steps:
            return
        self._browser_btn.setEnabled(False)
        self._browser_btn.setText("生成中…")
        try:
            from utils.html_anim import open_in_browser
            open_in_browser(self._question, self._steps)
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"无法生成动画页面：\n{e}")
        finally:
            self._browser_btn.setEnabled(True)
            self._browser_btn.setText("🌐  浏览器播放")

    # ── Cleanup ────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._auto_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(1000)
        super().closeEvent(event)


