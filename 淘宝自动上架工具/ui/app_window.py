# -*- coding: utf-8 -*-
"""主窗口 — PySide6 + qfluentwidgets Fluent Design"""
import asyncio
import json
import queue
import re
import socket
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition,
    FluentIcon as FIF, Theme, setTheme, setThemeColor,
    InfoBar, InfoBarPosition, MessageBox,
)
from loguru import logger


def _load_settings() -> dict:
    cfg = Path('config/settings.json')
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def _check_cdp(port: int) -> bool:
    try:
        with socket.create_connection(('localhost', port), timeout=0.5):
            return True
    except OSError:
        return False


class AppWindow(FluentWindow):
    """商业级主窗口（Fluent Design 深色主题）"""

    def __init__(self):
        super().__init__()
        setTheme(Theme.LIGHT)
        setThemeColor('#4F6EF7')

        self.setWindowTitle('淘宝自动上架工具  v2.0')
        self.resize(1460, 900)
        self.setMinimumSize(1100, 700)

        self._products  = []
        self._folder    = None
        self._running   = False
        self._queue     = None   # core.task_queue.TaskQueue，运行期设置
        self._msg_queue = queue.Queue()

        from ui.task_page     import TaskPage
        from ui.settings_page import SettingsPage

        self.task_page     = TaskPage(self)
        self.settings_page = SettingsPage(self)

        self._init_navigation()
        self._hook_logger()

        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._poll_queue)
        self._queue_timer.start(250)

        self._browser_timer = QTimer(self)
        self._browser_timer.timeout.connect(self._poll_browser)
        self._browser_timer.start(3000)
        self._poll_browser()

        # 若设置了默认文件夹，启动后自动加载
        QTimer.singleShot(500, self._auto_import)

    # ── 导航 ──────────────────────────────────────────────────────────────

    def _init_navigation(self):
        self.addSubInterface(self.task_page, FIF.DOCUMENT, '上架任务')
        self.addSubInterface(
            self.settings_page, FIF.SETTING, '设置',
            position=NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.setCurrentItem(self.task_page.objectName())

    def _auto_import(self):
        folder = _load_settings().get('default_folder', '').strip()
        if folder and Path(folder).is_dir():
            logger.info(f'自动加载默认文件夹: {folder}')
            self._do_import(folder)

    # ── 浏览器连接检测（后台线程，不阻塞主线程）────────────────────────────

    def _poll_browser(self):
        port = _load_settings().get('debug_port', 9222)
        def _check():
            ok = _check_cdp(port)
            self._msg_queue.put(('browser', ok))
        threading.Thread(target=_check, daemon=True).start()

    # ── 按钮回调 ───────────────────────────────────────────────────────────

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择商品数据文件夹')
        if not folder:
            return
        self._do_import(folder)

    def _do_import(self, folder: str):
        try:
            from core.data_reader import scan_and_read_folder
            from core.image_processor import load_product_images
            products = scan_and_read_folder(folder)
            for p in products:
                load_product_images(p)
            self._products = products
            self._folder   = folder
            self.task_page.load_products(products, Path(folder).name)
            logger.info(f'导入文件夹: {folder}  共 {len(products)} 个商品')
        except Exception as e:
            InfoBar.error('导入失败', str(e), parent=self,
                          position=InfoBarPosition.TOP_RIGHT, duration=5000)

    def start_upload(self):
        if not self._products:
            InfoBar.warning('提示', '请先导入商品数据文件夹', parent=self,
                            position=InfoBarPosition.TOP_RIGHT)
            return
        cfg = _load_settings()
        port = cfg.get('debug_port', 9222)
        if not _check_cdp(port):
            box = MessageBox(
                '浏览器未连接',
                f'未检测到调试模式浏览器（端口 {port}）。\n\n'
                '请先点击「启动调试浏览器」并登录淘宝，再开始上架。\n\n'
                '确认浏览器已就绪，仍要继续吗？',
                self,
            )
            if not box.exec():
                return
        self._running = True
        self.task_page.set_running(True)
        threading.Thread(target=self._run_upload_thread, daemon=True).start()

    def pause_upload(self):
        if self._queue is None:
            return
        if self._queue.is_paused:
            self._queue.resume()
            self.task_page.set_paused(False)
            logger.info('继续上架')
        else:
            self._queue.pause()
            self.task_page.set_paused(True)
            logger.info('上架已暂停')

    def stop_upload(self):
        if self._queue:
            self._queue.cancel()
        self._running = False
        self.task_page.set_running(False)
        InfoBar.warning('已停止', '上架任务已手动停止', parent=self,
                        position=InfoBarPosition.TOP_RIGHT, duration=3000)

    def open_report(self):
        import subprocess
        reports = sorted(Path('data').glob('上架报告_*.xlsx'), reverse=True)
        if not reports:
            InfoBar.info('提示', '暂无报告文件', parent=self,
                         position=InfoBarPosition.TOP_RIGHT)
            return
        subprocess.Popen(['explorer', str(reports[0])], shell=True)

    def retry_failed(self):
        from models.product import TaskStatus
        for p in self._products:
            if p.status == TaskStatus.FAILED:
                p.status = TaskStatus.PENDING
                p.error  = ''
        self.task_page.load_products(self._products, Path(self._folder).name)
        self.start_upload()

    def launch_browser(self):
        import subprocess
        bat = Path('启动调试浏览器.bat').resolve()
        if bat.exists():
            subprocess.Popen(str(bat), shell=True, cwd=str(bat.parent))
            logger.info('已启动调试浏览器，请登录淘宝后点击「开始上架」')
        else:
            InfoBar.error('找不到文件', f'找不到启动脚本: {bat}', parent=self,
                          position=InfoBarPosition.TOP_RIGHT, duration=5000)

    # ── 上架线程（直连 CDP，不经 Scheduler）───────────────────────────────

    def _run_upload_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_upload_async())
            self._msg_queue.put(('done', None))
        except Exception as e:
            self._msg_queue.put(('error', str(e)))
        finally:
            loop.close()

    async def _run_upload_async(self):
        from core.browser import BrowserEngine
        from core.uploader import TaobaoUploader
        from core.task_queue import TaskQueue
        from models.product import TaskStatus

        cfg = _load_settings()
        shipping_tpl = cfg.get('shipping_tpl', '光阴童话')

        engine = BrowserEngine(account_name='taobao')
        await engine.start()

        self._queue = TaskQueue(self._products)
        # TaskQueue.__init__ 会从 task_state.json 恢复状态（断点续传），
        # 但 GUI 每次点「开始上架」都应全量重新上架，在此强制重置。
        for p in self._products:
            p.status  = TaskStatus.PENDING
            p.error   = ''
            p.item_id = ''
        uploader    = TaobaoUploader(engine)

        try:
            for product in self._queue:
                if self._queue.is_cancelled:
                    break
                while self._queue.is_paused:
                    await asyncio.sleep(0.5)

                product.shipping_tpl = shipping_tpl
                product.status = TaskStatus.RUNNING
                self._msg_queue.put(('update', product))

                try:
                    await uploader.upload(product)
                except Exception as e:
                    product.error = str(e)
                    product.status = TaskStatus.FAILED

                self._queue.save_state()
                self._msg_queue.put(('update', product))
        finally:
            try:
                await engine.close()
            except Exception:
                pass
            self._queue = None

    # ── 消息队列轮询（主线程）──────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg_type, payload = self._msg_queue.get_nowait()
                if msg_type == 'update':
                    self.task_page.update_product(payload)
                    self.task_page.refresh_stats(self._products)
                elif msg_type == 'step':
                    seq, step_text = payload
                    self.task_page.update_step(seq, step_text, self._products)
                elif msg_type == 'log':
                    t, level, msg = payload
                    self.task_page.append_log(t, level, msg)
                elif msg_type == 'done':
                    self._on_done(success=True)
                elif msg_type == 'error':
                    self._on_done(success=False)
                    InfoBar.error('运行错误', payload, parent=self,
                                  position=InfoBarPosition.TOP_RIGHT, duration=0)
                elif msg_type == 'browser':
                    self.task_page.set_browser_status(payload)
        except queue.Empty:
            pass

    def _on_done(self, success: bool = True):
        self._running = False
        self.task_page.set_running(False)
        self.task_page.reset_progress()
        from models.product import TaskStatus
        has_failed = any(p.status == TaskStatus.FAILED for p in self._products)
        self.task_page.set_retry_enabled(has_failed)
        if success:
            InfoBar.success('上架完成', '所有任务已完成，请查看报告',
                            parent=self, position=InfoBarPosition.TOP_RIGHT,
                            duration=5000)

    # ── loguru → 消息队列桥接 ─────────────────────────────────────────────

    def _hook_logger(self):
        q = self._msg_queue

        def _sink(message):
            rec   = message.record
            t     = rec['time'].strftime('%H:%M:%S')
            level = rec['level'].name
            text  = rec['message']
            m = re.match(r'〔步骤:(.+?)〕(.+)', text)
            if m:
                seq, step = m.group(1), m.group(2).strip()
                q.put(('step', (seq, step)))
                q.put(('log',  (t, 'DEBUG', f'[步骤] {step}')))
                return
            q.put(('log', (t, level, text)))

        logger.add(_sink, level='DEBUG')
