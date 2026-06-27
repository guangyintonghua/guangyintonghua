"""启动闪屏"""
from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QGradient

from ui.styles import PALETTE


def _make_pixmap(w: int = 480, h: int = 280) -> QPixmap:
    px = QPixmap(w, h)
    px.fill(QColor(0, 0, 0, 0))

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 渐变背景
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0.0, QColor("#4B7BEC"))
    grad.setColorAt(1.0, QColor("#2D5BE3"))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, w, h, 20, 20)

    # 图标圆圈
    p.setBrush(QColor(255, 255, 255, 30))
    p.drawEllipse(w - 120, -40, 160, 160)
    p.setBrush(QColor(255, 255, 255, 15))
    p.drawEllipse(w - 60, h - 60, 120, 120)

    # 主标题
    title_font = QFont("Microsoft YaHei UI", 26, QFont.Weight.Bold)
    title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    p.setFont(title_font)
    p.setPen(QColor(255, 255, 255))
    p.drawText(40, 80, "小学数学")

    sub_font = QFont("Microsoft YaHei UI", 16)
    p.setFont(sub_font)
    p.setPen(QColor(255, 255, 255, 200))
    p.drawText(40, 115, "智能练习系统")

    # 版本 & 副标题
    small_font = QFont("Microsoft YaHei UI", 9)
    p.setFont(small_font)
    p.setPen(QColor(255, 255, 255, 150))
    p.drawText(40, 145, "人教版  ·  AI驱动  ·  知识点精准分析")

    # 分隔线
    p.setPen(QColor(255, 255, 255, 60))
    p.drawLine(40, 170, w - 40, 170)

    # 加载文字占位（动态更新）
    p.setFont(QFont("Microsoft YaHei UI", 10))
    p.setPen(QColor(255, 255, 255, 180))
    p.drawText(40, h - 30, "正在初始化...")

    p.end()
    return px


class SplashScreen(QSplashScreen):
    def __init__(self):
        px = _make_pixmap()
        super().__init__(px, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint
        )

    def set_status(self, msg: str):
        # 在底部写状态文字
        px = _make_pixmap()
        p = QPainter(px)
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.setPen(QColor(255, 255, 255, 200))
        p.drawText(40, px.height() - 30, msg)
        p.end()
        self.setPixmap(px)
        QApplication.processEvents()


def show_splash() -> SplashScreen:
    sp = SplashScreen()
    sp.show()
    QApplication.processEvents()
    return sp
