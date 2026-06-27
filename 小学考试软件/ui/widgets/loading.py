"""
加载遮罩与旋转动画组件
商业级：半透明覆盖层 + 中心卡片 + 旋转圆弧 + 状态文字
"""
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush

from ui.styles import PALETTE


class Spinner(QWidget):
    """旋转加载指示器"""
    def __init__(self, size: int = 40, color: str = None, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._color = QColor(color or PALETTE["primary"])
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start(16)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = self.width()
        margin = size // 8
        rect = QRect(margin, margin, size - 2 * margin, size - 2 * margin)

        # 背景弧（浅色）
        bg_pen = QPen(QColor(self._color.red(), self._color.green(),
                             self._color.blue(), 40))
        bg_pen.setWidth(size // 10)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bg_pen)
        p.drawArc(rect, 0, 360 * 16)

        # 前景弧（彩色）
        fg_pen = QPen(self._color)
        fg_pen.setWidth(size // 10)
        fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(fg_pen)
        p.drawArc(rect, -self._angle * 16, 270 * 16)


class LoadingOverlay(QWidget):
    """全屏半透明遮罩 + 中心提示卡"""
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0,0,0,0);")
        self.hide()

        # 中心卡片
        self._card = QWidget(self)
        self._card.setFixedSize(200, 140)
        self._card.setStyleSheet(
            f"background: {PALETTE['card']}; border-radius: 16px;"
        )

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._spinner = Spinner(48, PALETTE["primary"])
        card_layout.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("处理中...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            f"font-family: 'Microsoft YaHei UI'; font-size: 13px; "
            f"color: {PALETTE['text_secondary']}; background: transparent;"
        )
        card_layout.addWidget(self._label)

    def show_loading(self, message: str = "处理中..."):
        self.resize(self.parent().size())
        self._label.setText(message)
        self._spinner.start()
        self._position_card()
        self.raise_()
        self.show()

    def hide_loading(self):
        self._spinner.stop()
        self.hide()

    def set_message(self, msg: str):
        self._label.setText(msg)

    def _position_card(self):
        pw, ph = self.parent().width(), self.parent().height()
        cw, ch = self._card.width(), self._card.height()
        self._card.move((pw - cw) // 2, (ph - ch) // 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_card()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))
