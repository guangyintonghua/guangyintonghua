from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QPainter, QColor,
    QLinearGradient, QBrush, QPainterPath
)
import qtawesome as qta

import config
from ui.styles import PALETTE


def _make_icon_badge(fa_name: str, c1: str, c2: str, size: int = 36) -> QPixmap:
    """渐变圆角正方形 + 白色 FA 矢量图标。"""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    grad = QLinearGradient(0.0, 0.0, float(size), float(size))
    grad.setColorAt(0.0, QColor(c1))
    grad.setColorAt(1.0, QColor(c2))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), 9, 9)
    p.fillPath(path, QBrush(grad))

    ico_sz = int(size * 0.56)
    ico_px = qta.icon(fa_name, color="white").pixmap(ico_sz, ico_sz)
    off = (size - ico_sz) // 2
    p.drawPixmap(off, off, ico_px)
    p.end()
    return px
from ui.pages.home_page import HomePage
from ui.pages.exam_page import ExamPage
from ui.pages.submit_page import SubmitPage
from ui.pages.report_page import ReportPage
from ui.pages.practice_page import PracticePage
from ui.pages.settings_page import SettingsPage
from ui.pages.wrong_book_page import WrongBookPage
from ui.pages.speed_calc_page import SpeedCalcPage


# (key, fa_icon, gradient_start, gradient_end, label)
NAV_ITEMS = [
    ("home",       "fa5s.home",         "#5B8DEF", "#3867D6", "首页"),
    ("exam",       "fa5s.pencil-alt",   "#FD9644", "#E67E22", "出题"),
    ("submit",     "fa5s.camera",       "#B07FFF", "#8854D0", "批改"),
    ("report",     "fa5s.chart-bar",    "#26DE81", "#20BF6B", "分析"),
    ("practice",   "fa5s.bullseye",     "#FC5C65", "#C0392B", "专练"),
    ("wrong_book", "fa5s.book-open",    "#2BCBBA", "#0FB9B1", "错题本"),
    ("speed_calc", "fa5s.bolt",         "#FDCB6E", "#F9CA24", "口算"),
    ("settings",   "fa5s.cog",          "#A5B1C2", "#778CA3", "设置"),
]


class SidebarNavItem(QFrame):
    """矢量图标 + 渐变徽章的侧边栏导航按钮"""
    nav_clicked = pyqtSignal()

    def __init__(self, fa_name: str, c1: str, c2: str,
                 label: str, parent=None):
        super().__init__(parent)
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(11)

        # 渐变矢量图标徽章 —— 延迟绘制（QApplication 启动后调用）
        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(34, 34)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent;")
        self._fa_name, self._c1, self._c2 = fa_name, c1, c2
        layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(label)
        self._text_lbl.setStyleSheet(
            f"font-size:14px;color:{PALETTE['text_secondary']};background:transparent;"
        )
        layout.addWidget(self._text_lbl, 1)

        self._set_style()

    def showEvent(self, event):
        # 第一次显示时才渲染图标，确保 QApplication 已就绪
        if self._icon_lbl.pixmap() is None or self._icon_lbl.pixmap().isNull():
            self._icon_lbl.setPixmap(_make_icon_badge(self._fa_name, self._c1, self._c2, 34))
        super().showEvent(event)

    def set_active(self, active: bool):
        self._active = active
        self._set_style()

    def _set_style(self):
        if self._active:
            self.setStyleSheet(
                f"SidebarNavItem{{background:{PALETTE['primary_light']};"
                f"border-radius:10px;}}"
            )
            self._text_lbl.setStyleSheet(
                f"font-size:14px;font-weight:bold;color:{PALETTE['primary']};"
                f"background:transparent;"
            )
        else:
            self.setStyleSheet("SidebarNavItem{background:transparent;border-radius:10px;}")
            self._text_lbl.setStyleSheet(
                f"font-size:14px;color:{PALETTE['text_secondary']};background:transparent;"
            )

    def enterEvent(self, event):
        if not self._active:
            self.setStyleSheet(
                f"SidebarNavItem{{background:{PALETTE['bg']};border-radius:10px;}}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._set_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.nav_clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小学数学智能练习系统")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 侧边栏
        self._sidebar = self._build_sidebar()
        layout.addWidget(self._sidebar)

        # 右侧内容区
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # 实例化各页面
        self._pages: dict[str, QWidget] = {}
        self._home_page = HomePage(self)
        self._exam_page = ExamPage(self)
        self._submit_page = SubmitPage(self)
        self._report_page = ReportPage(self)
        self._practice_page = PracticePage(self)
        self._wrong_book_page = WrongBookPage(self)
        self._speed_calc_page = SpeedCalcPage(self)
        self._settings_page = SettingsPage(self)

        pages_map = {
            "home":       self._home_page,
            "exam":       self._exam_page,
            "submit":     self._submit_page,
            "report":     self._report_page,
            "practice":   self._practice_page,
            "wrong_book": self._wrong_book_page,
            "speed_calc": self._speed_calc_page,
            "settings":   self._settings_page,
        }
        for key, page in pages_map.items():
            self._pages[key] = page
            self._stack.addWidget(page)

        self._nav_buttons: dict[str, QPushButton] = {}
        self._current_page = ""

        # 渲染 logo 图标（QApplication 已就绪后）
        self._logo_icon.setPixmap(_make_icon_badge("fa5s.calculator", "#5B8DEF", "#8854D0", 42))

        self.navigate("home")

        # 页面间信号连接
        self._home_page.open_exam_requested.connect(lambda: self.navigate("exam"))
        self._home_page.open_submit_requested.connect(
            lambda exam_id: self._navigate_submit(exam_id)
        )
        self._home_page.open_report_requested.connect(
            lambda sub_id: self._navigate_report(sub_id)
        )
        self._exam_page.exam_created.connect(self._on_exam_created)
        self._submit_page.submission_done.connect(self._on_submission_done)
        self._report_page.open_practice_requested.connect(
            lambda kp: self._navigate_practice(kp)
        )

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo 区域 ──────────────────────────
        logo_area = QWidget()
        logo_area.setFixedHeight(88)
        logo_layout = QHBoxLayout(logo_area)
        logo_layout.setContentsMargins(14, 16, 14, 12)
        logo_layout.setSpacing(11)

        self._logo_icon = QLabel()
        self._logo_icon.setFixedSize(42, 42)
        self._logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_icon.setStyleSheet("background:transparent;")
        logo_layout.addWidget(self._logo_icon)

        logo_text = QVBoxLayout()
        logo_text.setSpacing(2)
        title_lbl = QLabel("数学练习")
        title_lbl.setStyleSheet(
            f"font-size:15px;font-weight:bold;color:{PALETTE['primary']};"
            f"background:transparent;"
        )
        sub_lbl = QLabel("人教版 · 智能分析")
        sub_lbl.setStyleSheet(
            f"font-size:10px;color:{PALETTE['text_hint']};background:transparent;"
        )
        logo_text.addWidget(title_lbl)
        logo_text.addWidget(sub_lbl)
        logo_layout.addLayout(logo_text, 1)
        layout.addWidget(logo_area)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{PALETTE['border']};")
        layout.addWidget(line)
        layout.addSpacing(6)

        # ── 导航项 ─────────────────────────────
        self._nav_items: dict[str, SidebarNavItem] = {}
        for key, fa, c1, c2, label in NAV_ITEMS:
            item = SidebarNavItem(fa, c1, c2, label)
            item.nav_clicked.connect(lambda k=key: self.navigate(k))
            wrap = QWidget()
            wrap_layout = QHBoxLayout(wrap)
            wrap_layout.setContentsMargins(8, 1, 8, 1)
            wrap_layout.addWidget(item)
            layout.addWidget(wrap)
            self._nav_items[key] = item

        layout.addStretch()

        # ── 底部学生信息 ───────────────────────
        student_widget = QWidget()
        student_layout = QVBoxLayout(student_widget)
        student_layout.setContentsMargins(14, 8, 14, 16)
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(f"color:{PALETTE['border']};")
        student_layout.addWidget(line2)

        self._student_label = QLabel()
        self._student_label.setStyleSheet(
            f"color:{PALETTE['text_secondary']};font-size:12px;"
            f"background:transparent;"
        )
        self._student_label.setWordWrap(True)
        self._refresh_student_label()
        student_layout.addWidget(self._student_label)
        layout.addWidget(student_widget)

        return sidebar

    def _refresh_student_label(self):
        from data.database import get_student
        sid = config.get("default_student_id")
        if sid:
            s = get_student(int(sid))
            if s:
                self._student_label.setText(f"👤 {s['name']}\n{s['grade']}")
                return
        self._student_label.setText("👤 未选择学生\n请到设置中配置")

    def navigate(self, page_key: str):
        if page_key not in self._pages:
            return
        for key, item in self._nav_items.items():
            item.set_active(key == page_key)

        self._stack.setCurrentWidget(self._pages[page_key])
        self._current_page = page_key

        page = self._pages[page_key]
        if hasattr(page, "on_activate"):
            page.on_activate()

    def _navigate_submit(self, exam_id: int):
        self._submit_page.load_exam(exam_id)
        self.navigate("submit")

    def _navigate_report(self, sub_id: int):
        self._report_page.load_submission(sub_id)
        self.navigate("report")

    def _navigate_practice(self, knowledge_point: str):
        self._practice_page.start_practice(knowledge_point)
        self.navigate("practice")

    def _on_exam_created(self, exam_id: int):
        self._submit_page.load_exam(exam_id)
        self.navigate("submit")

    def _on_submission_done(self, sub_id: int):
        self._report_page.load_submission(sub_id)
        self.navigate("report")
        self._home_page.refresh()

    def refresh_student(self):
        self._refresh_student_label()
        self._home_page.refresh()
