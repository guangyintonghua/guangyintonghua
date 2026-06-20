"""GUI 启动入口"""
import sys
from pathlib import Path
from loguru import logger

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

Path('logs').mkdir(exist_ok=True)
logger.add('logs/run_{time:YYYYMMDD_HHmmss}.log',
           level='DEBUG', encoding='utf-8',
           rotation='50 MB', retention='30 days')

if __name__ == '__main__':
    logger.info('=== 启动 淘宝自动上架工具 ===')
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setApplicationName('淘宝自动上架工具')
        _ico = Path('assets/app_icon.ico')
        if _ico.exists():
            app.setWindowIcon(QIcon(str(_ico)))

        from ui.app_window import AppWindow
        window = AppWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.exception(f'启动失败: {e}')
        raise
