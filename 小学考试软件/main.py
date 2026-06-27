import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# ── 日志最先初始化 ────────────────────────────
from utils import logger as _logger
log = _logger.setup()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

import config
from data.database import init_db
from utils.cache import clear_expired


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("小学数学智能练习系统")
    app.setOrganizationName("EduTools")
    app.setApplicationVersion("1.0.0")

    # 全局字体
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)

    # ── 闪屏 ─────────────────────────────────
    from ui.splash import show_splash
    splash = show_splash()

    splash.set_status("初始化数据库...")
    init_db()

    splash.set_status("清理过期缓存...")
    try:
        clear_expired()
    except Exception:
        pass

    splash.set_status("写入默认配置...")
    if not config.get("api_key"):
        config.set_value("api_key", "sk-40c9751c22c14ef4ae78acb990cdf1ca")

    splash.set_status("加载界面样式...")
    from ui.styles import MAIN_QSS
    app.setStyleSheet(MAIN_QSS)

    splash.set_status("启动主窗口...")
    from ui.main_window import MainWindow
    window = MainWindow()

    # ── 首次运行引导 ──────────────────────────
    from ui.onboarding import should_onboard, run_onboarding
    splash.finish(window)
    window.show()

    if should_onboard():
        log.info("First run detected, starting onboarding")
        QTimer.singleShot(300, lambda: _do_onboard(window))
    else:
        log.info("Main window ready")

    sys.exit(app.exec())


def _do_onboard(window):
    from ui.onboarding import run_onboarding
    if run_onboarding(window):
        window.refresh_student()


if __name__ == "__main__":
    main()
