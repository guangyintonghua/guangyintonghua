"""主窗口 — 浅色极简设计"""
import asyncio
import json
import queue
import re
import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from loguru import logger

from ui.styles import (
    BG_MAIN, BG_CARD, BG_SIDEBAR, BG_HOVER,
    PRIMARY, PRIMARY_HOVER, PRIMARY_LIGHT, PRIMARY_DARK,
    ACCENT,
    SUCCESS, DANGER, WARNING, MUTED,
    BORDER, BORDER_MID,
    TEXT_H, TEXT_BODY, TEXT_MUTED, TEXT_HINT,
    hover_color,
)
from ui.task_panel    import TaskPanel
from ui.log_panel     import LogPanel
from ui.account_panel import AccountPanel
from core.account_manager import AccountManager


_STEPS     = ['导航', '标题', '主图', '详情图', '属性', '规格', '物流', '价格', '提交']
_STEP_NUMS = ['01', '02', '03', '04', '05', '06', '07', '08', '09']


# ── 按钮工厂 ──────────────────────────────────────────────────────────────────

def _primary_btn(parent, text, cmd=None, state='normal'):
    """近黑主按钮"""
    btn = tk.Button(parent, text=text,
                    font=('Microsoft YaHei UI', 10),
                    bg=PRIMARY, fg='#FFFFFF', relief='flat', bd=0,
                    activebackground=PRIMARY_HOVER, activeforeground='#FFFFFF',
                    padx=16, pady=7, cursor='hand2',
                    disabledforeground='#71717A',
                    command=cmd, state=state)

    def _on(e):
        if str(btn['state']) != 'disabled':
            btn.configure(bg=PRIMARY_HOVER)
    def _off(e):
        if str(btn['state']) != 'disabled':
            btn.configure(bg=PRIMARY)

    btn.bind('<Enter>', _on)
    btn.bind('<Leave>', _off)
    btn.pack(side='left', padx=(0, 2), pady=8)
    return btn


def _ghost_btn(parent, text, fg=TEXT_BODY, cmd=None, state='normal'):
    """幽灵按钮：透明底 + 细边框"""
    frm = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    frm.pack(side='left', padx=(0, 2), pady=8)
    btn = tk.Button(frm, text=text,
                    font=('Microsoft YaHei UI', 10),
                    bg=BG_CARD, fg=fg, relief='flat', bd=0,
                    activebackground=BG_HOVER, activeforeground=fg,
                    padx=14, pady=6, cursor='hand2',
                    command=cmd, state=state)
    btn.pack()
    btn.bind('<Enter>', lambda e: btn.configure(bg=BG_HOVER) if str(btn['state']) != 'disabled' else None)
    btn.bind('<Leave>', lambda e: btn.configure(bg=BG_CARD) if str(btn['state']) != 'disabled' else None)
    frm._btn = btn
    return frm


def _sep(parent):
    tk.Frame(parent, bg=BORDER, width=1, height=20).pack(side='left', padx=8, pady=12)


def _check_cdp_port(port: int) -> bool:
    try:
        with socket.create_connection(('localhost', port), timeout=0.5):
            return True
    except OSError:
        return False


def _get_debug_port() -> int:
    cfg = Path('config/settings.json')
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding='utf-8')).get('debug_port', 9222)
        except Exception:
            pass
    return 9222


# ── 主窗口 ────────────────────────────────────────────────────────────────────

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('淘宝自动上架工具')
        self.geometry('1300x820')
        self.minsize(1060, 680)
        self.configure(bg=BG_MAIN)

        self._am          = AccountManager()
        self._scheduler   = None
        self._products    = []
        self._data_folder = None
        self._excel_path  = None
        self._running     = False
        self._msg_queue   = queue.Queue()

        self._build_ui()
        self._hook_logger()
        self._poll_queue()
        self._poll_browser_status()

    # ── UI 构建 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── 顶部导航栏 (纯白 + 底边框) ──────────────────────────────────────
        nav = tk.Frame(self, bg=BG_CARD, height=52)
        nav.pack(fill='x')
        nav.pack_propagate(False)

        # 左侧 logo 区
        logo_area = tk.Frame(nav, bg=BG_CARD, width=200)
        logo_area.pack(side='left', fill='y')
        logo_area.pack_propagate(False)

        tk.Label(logo_area, text='自动上架',
                 font=('Microsoft YaHei UI', 13, 'bold'),
                 bg=BG_CARD, fg=TEXT_H).pack(side='left', padx=(20, 0), pady=16)

        # 竖向分隔
        tk.Frame(nav, bg=BORDER, width=1).pack(side='left', fill='y', pady=14)

        # 版本标签
        tk.Label(nav, text='淘宝商品上架工具  v1.0',
                 font=('Microsoft YaHei UI', 10),
                 bg=BG_CARD, fg=TEXT_MUTED).pack(side='left', padx=16, pady=16)

        # 右侧状态标签
        self._lbl_status = tk.Label(nav, text='请导入商品文件夹',
                                     font=('Microsoft YaHei UI', 10),
                                     bg=BG_CARD, fg=TEXT_HINT)
        self._lbl_status.pack(side='right', padx=20, pady=16)

        # 导航栏底边框
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x')

        # ── 主体区域 ────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG_MAIN)
        body.pack(fill='both', expand=True)

        # ── 左侧边栏 (浅灰) ─────────────────────────────────────────────────
        sidebar = tk.Frame(body, bg=BG_SIDEBAR, width=200)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)

        # 侧边栏右边框
        tk.Frame(body, bg=BORDER, width=1).pack(side='left', fill='y')

        self._account_panel = AccountPanel(sidebar, self._am)
        self._account_panel.pack(fill='x')

        self._build_browser_status(sidebar)

        tk.Label(sidebar, text='© 2026 光阴童话',
                 font=('Microsoft YaHei UI', 8),
                 bg=BG_SIDEBAR, fg=TEXT_HINT).pack(side='bottom', pady=12)

        # ── 右侧主区 ─────────────────────────────────────────────────────────
        right = tk.Frame(body, bg=BG_MAIN)
        right.pack(side='left', fill='both', expand=True)

        # ── 工具栏 ────────────────────────────────────────────────────────────
        toolbar_wrap = tk.Frame(right, bg=BG_MAIN, padx=14, pady=10)
        toolbar_wrap.pack(fill='x')

        toolbar = tk.Frame(toolbar_wrap, bg=BG_CARD,
                           highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill='x')

        # 主要操作
        self._btn_import = _primary_btn(toolbar, '  导入文件夹  ', cmd=self._import_folder)
        _sep(toolbar)
        self._btn_start  = _primary_btn(toolbar, '  开始上架  ', cmd=self._start, state='disabled')

        # 次级操作
        self._btn_pause  = _ghost_btn(toolbar, '暂停', fg=WARNING,  cmd=self._pause, state='disabled')
        self._btn_stop   = _ghost_btn(toolbar, '停止', fg=DANGER,   cmd=self._stop,  state='disabled')
        _sep(toolbar)
        self._btn_report = _ghost_btn(toolbar, '查看报告', cmd=self._open_report)
        self._btn_retry  = _ghost_btn(toolbar, '重试失败', fg=TEXT_MUTED, cmd=self._retry, state='disabled')

        # ── 步骤进度卡片 ──────────────────────────────────────────────────────
        self._build_progress_card(right)

        # ── 任务列表 + 日志（可拖拽分隔）─────────────────────────────────────
        pane = tk.PanedWindow(right, orient='vertical', bg=BORDER,
                              sashwidth=5, sashrelief='flat', sashpad=1)
        pane.pack(fill='both', expand=True, padx=14, pady=(0, 10))

        self._task_panel = TaskPanel(pane)
        self._log_panel  = LogPanel(pane)
        pane.add(self._task_panel, minsize=280)
        pane.add(self._log_panel,  minsize=100)
        pane.paneconfigure(self._task_panel, height=460)
        pane.paneconfigure(self._log_panel,  height=160)

    def _build_browser_status(self, parent):
        """侧边栏浏览器连接状态区（浅色）"""
        # 分隔线
        tk.Frame(parent, bg=BORDER, height=1).pack(fill='x', padx=10, pady=(14, 0))

        hdr = tk.Frame(parent, bg=BG_SIDEBAR)
        hdr.pack(fill='x', padx=16, pady=(12, 6))
        tk.Label(hdr, text='浏览器',
                 font=('Microsoft YaHei UI', 9, 'bold'),
                 bg=BG_SIDEBAR, fg=PRIMARY).pack(anchor='w')

        # 卡片（带边框）
        outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        outer.pack(fill='x', padx=10)
        card = tk.Frame(outer, bg=BG_CARD, padx=12, pady=10)
        card.pack(fill='both')

        # 状态行
        status_row = tk.Frame(card, bg=BG_CARD)
        status_row.pack(fill='x')

        self._browser_dot = tk.Frame(status_row, bg=MUTED, width=7, height=7)
        self._browser_dot.pack(side='left', padx=(0, 8))
        self._browser_dot.pack_propagate(False)
        self._browser_lbl = tk.Label(status_row, text='未连接',
                                      font=('Microsoft YaHei UI', 10),
                                      bg=BG_CARD, fg=TEXT_MUTED)
        self._browser_lbl.pack(side='left')

        port = _get_debug_port()
        tk.Label(card, text=f'端口 {port}',
                 font=('Microsoft YaHei UI', 8),
                 bg=BG_CARD, fg=TEXT_HINT).pack(anchor='w', pady=(3, 6))

        # 启动浏览器按钮
        outer2 = tk.Frame(card, bg=BORDER, padx=1, pady=1)
        outer2.pack(fill='x')
        launch_btn = tk.Button(outer2, text='启动调试浏览器',
                               font=('Microsoft YaHei UI', 9),
                               bg=BG_CARD, fg=PRIMARY, relief='flat', bd=0,
                               activebackground=PRIMARY_LIGHT, activeforeground=PRIMARY_HOVER,
                               padx=8, pady=5, cursor='hand2',
                               command=self._launch_debug_browser)
        launch_btn.pack(fill='x')
        launch_btn.bind('<Enter>', lambda e: launch_btn.configure(bg=PRIMARY_LIGHT))
        launch_btn.bind('<Leave>', lambda e: launch_btn.configure(bg=BG_CARD))

    def _build_progress_card(self, parent):
        """步骤进度卡片"""
        card = tk.Frame(parent, bg=BG_CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill='x', padx=14, pady=(0, 6))

        # 顶行：状态点 + 商品名 + 进度计数
        row1 = tk.Frame(card, bg=BG_CARD)
        row1.pack(fill='x', padx=14, pady=(9, 0))

        self._step_dot = tk.Label(row1, text='',
                                   font=('Microsoft YaHei UI', 8),
                                   bg=BG_CARD, fg=MUTED, width=0)
        # hidden — kept for compatibility with _update_step_display

        self._lbl_step_product = tk.Label(
            row1, text='待机中  —  导入商品数据后点击「开始上架」',
            font=('Microsoft YaHei UI', 10),
            bg=BG_CARD, fg=TEXT_MUTED)
        self._lbl_step_product.pack(side='left')

        self._lbl_step_count = tk.Label(row1, text='',
                                         font=('Microsoft YaHei UI', 9),
                                         bg=BG_CARD, fg=TEXT_HINT)
        self._lbl_step_count.pack(side='right', padx=4)

        # 中行：步骤药丸
        row2 = tk.Frame(card, bg=BG_CARD)
        row2.pack(fill='x', padx=14, pady=(6, 0))

        self._step_pills = []
        for num, name in zip(_STEP_NUMS, _STEPS):
            pill = tk.Label(row2, text=f'{name}',
                            font=('Microsoft YaHei UI', 9),
                            bg=BG_MAIN, fg=TEXT_HINT,
                            padx=8, pady=3)
            pill.pack(side='left', padx=(0, 3))
            self._step_pills.append(pill)

        # 底行：详情
        row3 = tk.Frame(card, bg=BG_CARD)
        row3.pack(fill='x', padx=14, pady=(4, 9))

        self._lbl_step_detail = tk.Label(row3, text='',
                                          font=('Microsoft YaHei UI', 9),
                                          bg=BG_CARD, fg=TEXT_HINT)
        self._lbl_step_detail.pack(side='left')

    def _update_step_display(self, seq: str, step_text: str):
        pass  # dot hidden
        self._lbl_step_detail.configure(text=f'当前: {step_text}', fg=TEXT_MUTED)

        product = next((p for p in self._products if str(p.seq) == str(seq)), None)
        if product:
            title = product.title
            title_short = (title[:40] + '…') if len(title) > 40 else title
            self._lbl_step_product.configure(text=f'正在上架: {title_short}', fg=TEXT_BODY)
            from models.product import TaskStatus
            done  = sum(1 for p in self._products if p.status == TaskStatus.DONE)
            total = len(self._products)
            self._lbl_step_count.configure(text=f'{done} / {total}', fg=TEXT_MUTED)

        idx = next((i for i, s in enumerate(_STEPS) if step_text.startswith(s)), -1)
        for i, (pill, name) in enumerate(zip(self._step_pills, _STEPS)):
            if i < idx:
                # 已完成：绿底
                pill.configure(bg='#DCFCE7', fg='#15803D',
                               font=('Microsoft YaHei UI', 9),
                               text=f'✓ {name}')
            elif i == idx:
                # 当前：深色底
                display = step_text if len(step_text) <= 6 else step_text[:6]
                pill.configure(bg=PRIMARY, fg='#FFFFFF',
                               font=('Microsoft YaHei UI', 9, 'bold'),
                               text=display)
            else:
                # 待执行：浅灰
                pill.configure(bg=BG_MAIN, fg=TEXT_HINT,
                               font=('Microsoft YaHei UI', 9),
                               text=name)

        self._task_panel.update_step(seq, step_text)

    def _reset_step_display(self):
        self._lbl_step_product.configure(text='待机中  —  上架任务已结束', fg=TEXT_MUTED)
        self._lbl_step_count.configure(text='')
        self._lbl_step_detail.configure(text='')
        for pill, name in zip(self._step_pills, _STEPS):
            pill.configure(bg=BG_MAIN, fg=TEXT_HINT,
                           font=('Microsoft YaHei UI', 9), text=name)

    def _launch_debug_browser(self):
        import subprocess
        bat = Path('启动调试浏览器.bat').resolve()
        if bat.exists():
            subprocess.Popen(str(bat), shell=True, cwd=str(bat.parent))
            logger.info('已启动调试浏览器，请登录淘宝后点击「开始上架」')
        else:
            messagebox.showerror('找不到文件', f'找不到启动脚本:\n{bat}')

    # ── 浏览器状态轮询 ────────────────────────────────────────────────────────

    def _poll_browser_status(self):
        port      = _get_debug_port()
        connected = _check_cdp_port(port)
        if connected:
            self._browser_dot.configure(bg=SUCCESS)
            self._browser_lbl.configure(text='已连接', fg=SUCCESS)
        else:
            self._browser_dot.configure(bg=MUTED)
            self._browser_lbl.configure(text='未连接', fg=TEXT_HINT)
        self.after(3000, self._poll_browser_status)

    # ── 按钮回调 ──────────────────────────────────────────────────────────────

    def _import_folder(self):
        folder = filedialog.askdirectory(title='选择商品数据文件夹')
        if not folder:
            return
        try:
            from core.data_reader import scan_and_read_folder
            products = scan_and_read_folder(folder)
            self._products    = products
            self._excel_path  = folder
            self._data_folder = folder
            self._task_panel.load_products(self._products)
            self._btn_start.configure(state='normal')
            self._lbl_status.configure(
                text=f'已加载 {len(products)} 个商品  ·  {Path(folder).name}',
                fg=TEXT_BODY)
            logger.info(f'导入文件夹: {folder}  共 {len(products)} 个商品')
        except Exception as e:
            messagebox.showerror('导入失败', str(e))

    def _start(self):
        if not self._excel_path or not self._products:
            messagebox.showwarning('提示', '请先导入数据文件夹')
            return
        port = _get_debug_port()
        if not _check_cdp_port(port):
            ans = messagebox.askyesno(
                '浏览器未连接',
                f'未检测到调试模式浏览器（端口 {port}）。\n\n'
                '请先启动调试浏览器并登录淘宝，再点击开始上架。\n\n'
                '确认浏览器已就绪，仍要继续吗？'
            )
            if not ans:
                return
        self._running = True
        self._btn_start.configure(state='disabled')
        self._btn_pause._btn.configure(state='normal')
        self._btn_stop._btn.configure(state='normal')
        self._btn_import.configure(state='disabled')
        self._lbl_status.configure(text='上架中…', fg=PRIMARY)
        threading.Thread(target=self._run_scheduler, daemon=True).start()

    def _pause(self):
        if self._scheduler:
            if self._scheduler._queue and self._scheduler._queue.is_paused:
                self._scheduler.resume()
                self._btn_pause._btn.configure(text='暂停')
                self._lbl_status.configure(text='上架中…', fg=PRIMARY)
            else:
                self._scheduler.pause()
                self._btn_pause._btn.configure(text='继续')
                self._lbl_status.configure(text='已暂停', fg=WARNING)

    def _stop(self):
        if self._scheduler:
            self._scheduler.stop()
        self._running = False
        self._lbl_status.configure(text='已停止', fg=DANGER)
        self._reset_buttons()

    def _open_report(self):
        import subprocess
        reports = sorted(Path('data').glob('上架报告_*.xlsx'), reverse=True)
        if not reports:
            messagebox.showinfo('提示', '暂无报告文件')
            return
        subprocess.Popen(['explorer', str(reports[0])], shell=True)

    def _retry(self):
        from models.product import TaskStatus
        for p in self._products:
            if p.status == TaskStatus.FAILED:
                p.status = TaskStatus.PENDING
                p.error  = ''
        self._task_panel.load_products(self._products)
        self._start()

    # ── 调度器线程 ────────────────────────────────────────────────────────────

    def _run_scheduler(self):
        from core.scheduler import Scheduler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scheduler = Scheduler(excel_path=self._excel_path,
                                  data_root=self._data_folder)
            from core.task_queue import TaskQueue
            scheduler._queue = TaskQueue(self._products)
            self._scheduler  = scheduler
            loop.run_until_complete(self._run_with_callbacks(scheduler))
        except Exception as e:
            self._msg_queue.put(('error', str(e)))
        finally:
            loop.close()
            self._msg_queue.put(('done', None))

    async def _run_with_callbacks(self, scheduler):
        from core.uploader import TaobaoUploader
        orig_upload = TaobaoUploader.upload

        async def upload_with_notify(self_up, product):
            result = await orig_upload(self_up, product)
            scheduler._queue.save_state()
            self._msg_queue.put(('update', product))
            return result

        TaobaoUploader.upload = upload_with_notify
        try:
            await scheduler.run()
        finally:
            TaobaoUploader.upload = orig_upload

    # ── 消息队列轮询 ─────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg_type, payload = self._msg_queue.get_nowait()
                if msg_type == 'update':
                    self._task_panel.update_product(payload)
                    self._task_panel._refresh_stats(self._products)
                    self._account_panel.refresh()
                elif msg_type == 'step':
                    seq, step_text = payload
                    self._update_step_display(seq, step_text)
                elif msg_type == 'done':
                    self._on_done()
                elif msg_type == 'error':
                    messagebox.showerror('运行错误', payload)
                    self._on_done()
                elif msg_type == 'log':
                    t, level, msg = payload
                    self._log_panel.append(t, level, msg)
        except queue.Empty:
            pass
        self.after(300, self._poll_queue)

    def _on_done(self):
        self._running = False
        self._lbl_status.configure(text='上架完成', fg=SUCCESS)
        self._reset_step_display()
        self._reset_buttons()
        from models.product import TaskStatus
        has_failed = any(p.status == TaskStatus.FAILED for p in self._products)
        self._btn_retry._btn.configure(state='normal' if has_failed else 'disabled')
        messagebox.showinfo('完成', '上架任务已完成，请查看报告')

    def _reset_buttons(self):
        self._btn_start.configure(state='normal')
        self._btn_pause._btn.configure(state='disabled', text='暂停')
        self._btn_stop._btn.configure(state='disabled')
        self._btn_import.configure(state='normal')

    # ── loguru → GUI 日志桥接 ─────────────────────────────────────────────────

    def _hook_logger(self):
        msg_q = self._msg_queue

        def sink(message):
            record = message.record
            t      = record['time'].strftime('%H:%M:%S')
            level  = record['level'].name
            text   = record['message']

            m = re.match(r'〔步骤:(.+?)〕(.+)', text)
            if m:
                seq, step_text = m.group(1), m.group(2).strip()
                msg_q.put(('step', (seq, step_text)))
                msg_q.put(('log', (t, 'DEBUG', f'[步骤] {step_text}')))
                return

            msg_q.put(('log', (t, level, text)))

        logger.add(sink, level='DEBUG')
