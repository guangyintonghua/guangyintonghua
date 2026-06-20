# -*- coding: utf-8 -*-
"""上架任务页面"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QAbstractItemView,
)
from qfluentwidgets import (
    ScrollArea, PrimaryPushButton, PushButton,
    TransparentPushButton, FluentIcon as FIF,
    ProgressBar, BodyLabel, StrongBodyLabel, CaptionLabel,
    isDarkTheme, SimpleCardWidget,
)

from models.product import TaskStatus

_STEPS = ['导航', '标题', '主图', '详情图', '属性', '规格', '物流', '价格', '提交']

# ── 统一调色板（浅色主题）────────────────────────────────────────────────────
_C_BRAND   = '#4F6EF7'   # 靛蓝 — 主操作、进行中
_C_SUCCESS = '#059669'   # 翠绿 — 完成、已连接
_C_ERROR   = '#DC2626'   # 红   — 失败、错误
_C_WARN    = '#D97706'   # 琥珀 — 警告
_C_MUTED   = '#64748B'   # 灰   — 待机、次要文本
_C_TEXT    = '#1E293B'   # 深色 — 正文

# ── 统计卡片 ────────────────────────────────────────────────────────────────

class StatCard(SimpleCardWidget):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        self._num = QLabel('0', self)
        self._num.setAlignment(Qt.AlignmentFlag.AlignLeft)
        f = QFont('Microsoft YaHei UI', 28, QFont.Weight.Bold)
        self._num.setFont(f)
        self._num.setStyleSheet(f'color: {color};')

        self._title = CaptionLabel(title, self)
        self._title.setStyleSheet(f'color: {_C_MUTED}; font-size: 12px;')

        layout.addWidget(self._num)
        layout.addWidget(self._title)
        self.setMinimumWidth(130)

    def set_value(self, v: int):
        self._num.setText(str(v))


# ── 步骤胶囊 ────────────────────────────────────────────────────────────────

class StepPill(QLabel):
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self._name = name
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(24)
        self.setContentsMargins(10, 0, 10, 0)
        self._set_idle()

    def _set_idle(self):
        self.setText(self._name)
        self.setStyleSheet(
            f'border-radius: 12px; padding: 0 10px;'
            f'background: rgba(0,0,0,0.06); color: {_C_MUTED};'
            f'font-size: 12px;'
        )

    def set_done(self):
        self.setText(f'✓ {self._name}')
        self.setStyleSheet(
            f'border-radius: 12px; padding: 0 10px;'
            f'background: rgba(5,150,105,0.10); color: {_C_SUCCESS};'
            f'font-size: 12px;'
        )

    def set_active(self, text: str = None):
        self.setText(text or self._name)
        self.setStyleSheet(
            f'border-radius: 12px; padding: 0 10px;'
            f'background: {_C_BRAND}; color: #fff;'
            f'font-size: 12px; font-weight: 600;'
        )

    def reset(self):
        self._set_idle()


# ── 日志面板 ────────────────────────────────────────────────────────────────

_LEVEL_COLORS = {
    'DEBUG':   _C_MUTED,
    'INFO':    _C_TEXT,
    'SUCCESS': _C_SUCCESS,
    'WARNING': _C_WARN,
    'ERROR':   _C_ERROR,
    'CRITICAL':_C_ERROR,
}

class LogWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(3000)
        self.setFont(QFont('Consolas', 10))
        self.setStyleSheet(
            'QPlainTextEdit {'
            '  background: #F8FAFC; color: #374151;'
            '  border: none; padding: 8px 12px;'
            '}'
        )

    def append_line(self, time_str: str, level: str, msg: str):
        color = _LEVEL_COLORS.get(level, _C_TEXT)
        time_html = f'<span style="color:#9CA3AF">[{time_str}]</span>'
        msg_html  = f'<span style="color:{color}">{self._esc(msg)}</span>'
        self.appendHtml(f'{time_html} {msg_html}')
        self.ensureCursorVisible()

    @staticmethod
    def _esc(s: str) -> str:
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ── 任务列表表格 ──────────────────────────────────────────────────────────────

_COL_HEADERS = ['序号', '商品标题', 'SKU', '状态', '商品 ID', '备注']
_COL_WIDTHS  = [52, 340, 48, 90, 130, 220]

_STATUS_TEXT  = {
    TaskStatus.PENDING:  '待上架',
    TaskStatus.RUNNING:  '上架中',
    TaskStatus.DONE:     '✓ 完成',
    TaskStatus.FAILED:   '✗ 失败',
    TaskStatus.SKIPPED:  '已跳过',
}
_STATUS_COLOR = {
    TaskStatus.PENDING:  _C_MUTED,
    TaskStatus.RUNNING:  _C_BRAND,
    TaskStatus.DONE:     _C_SUCCESS,
    TaskStatus.FAILED:   _C_ERROR,
    TaskStatus.SKIPPED:  _C_MUTED,
}

class TaskTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, len(_COL_HEADERS), parent)
        self.setHorizontalHeaderLabels(_COL_HEADERS)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        hh = self.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for i, w in enumerate(_COL_WIDTHS):
            self.setColumnWidth(i, w)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.setStyleSheet('''
            QTableWidget {
                background: transparent;
                border: none;
                outline: none;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid rgba(0,0,0,0.05);
                color: #1E293B;
            }
            QTableWidget::item:selected {
                background: rgba(79,110,247,0.10);
            }
            QHeaderView::section {
                background: transparent;
                color: #64748B;
                font-size: 12px;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid rgba(0,0,0,0.08);
            }
        ''')
        self._seq_to_row: dict[str, int] = {}

    def load(self, products):
        self._seq_to_row.clear()
        self.setRowCount(0)
        for i, p in enumerate(products):
            self.insertRow(i)
            self._fill_row(i, p)
            self._seq_to_row[str(p.seq)] = i
        self.setRowCount(len(products))

    def update_product(self, product):
        row = self._seq_to_row.get(str(product.seq))
        if row is None:
            return
        self._fill_row(row, product)

    def update_step(self, seq: str, step_text: str):
        row = self._seq_to_row.get(str(seq))
        if row is None:
            return
        item = self.item(row, 3)
        if item:
            item.setText(step_text[:10])
            item.setForeground(QBrush(QColor(_C_BRAND)))

    def _fill_row(self, row: int, product):
        vals = [
            str(product.seq),
            product.title,
            str(len(product.skus)),
            _STATUS_TEXT.get(product.status, ''),
            product.item_id or '',
            product.error or '',
        ]
        for col, val in enumerate(vals):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if col == 3:
                c = _STATUS_COLOR.get(product.status, _C_MUTED)
                item.setForeground(QBrush(QColor(c)))
            self.setItem(row, col, item)
        self.setRowHeight(row, 40)


# ── 主页面 ────────────────────────────────────────────────────────────────────

class TaskPage(ScrollArea):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._win = window
        self.setObjectName('taskPage')
        self.setWidgetResizable(True)

        container = QWidget(self)
        self.setWidget(container)
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(12)

        self._build_toolbar()
        self._build_stats()
        self._build_progress_card()
        self._build_split_area()

    # ── 工具栏 ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        card = SimpleCardWidget(self)
        row  = QHBoxLayout(card)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(8)

        self._btn_import = PrimaryPushButton(FIF.FOLDER, '导入文件夹', self)
        self._btn_start  = PrimaryPushButton(FIF.PLAY,   '开始上架', self)
        self._btn_pause  = PushButton(FIF.PAUSE, '暂停', self)
        self._btn_stop   = PushButton(FIF.CLOSE, '停止', self)
        self._btn_report = PushButton(FIF.DOCUMENT, '查看报告', self)
        self._btn_retry  = PushButton(FIF.SYNC, '重试失败', self)
        self._btn_browser = PushButton(FIF.GLOBE, '启动浏览器', self)

        # 浏览器状态指示
        self._browser_badge = QLabel('● 未连接', self)
        self._browser_badge.setStyleSheet(f'color: {_C_MUTED}; font-size: 12px; padding: 0 8px;')

        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_retry.setEnabled(False)

        self._btn_import.clicked.connect(self._win.import_folder)
        self._btn_start.clicked.connect(self._win.start_upload)
        self._btn_pause.clicked.connect(self._win.pause_upload)
        self._btn_stop.clicked.connect(self._win.stop_upload)
        self._btn_report.clicked.connect(self._win.open_report)
        self._btn_retry.clicked.connect(self._win.retry_failed)
        self._btn_browser.clicked.connect(self._win.launch_browser)

        for btn in [self._btn_import, self._btn_start, self._btn_pause,
                    self._btn_stop, self._btn_report, self._btn_retry,
                    self._btn_browser]:
            btn.setFixedHeight(34)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet('color: rgba(0,0,0,0.10);')
        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet('color: rgba(0,0,0,0.10);')

        row.addWidget(self._btn_import)
        row.addWidget(self._btn_start)
        row.addWidget(sep)
        row.addWidget(self._btn_pause)
        row.addWidget(self._btn_stop)
        row.addWidget(sep2)
        row.addWidget(self._btn_report)
        row.addWidget(self._btn_retry)
        row.addStretch()
        row.addWidget(self._browser_badge)
        row.addWidget(self._btn_browser)

        self._layout.addWidget(card)

    # ── 统计行 ──────────────────────────────────────────────────────────────

    def _build_stats(self):
        row = QHBoxLayout()
        row.setSpacing(12)

        self._stat_total   = StatCard('总任务',  _C_TEXT,    self)
        self._stat_done    = StatCard('已完成',  _C_SUCCESS, self)
        self._stat_failed  = StatCard('失败',    _C_ERROR,   self)
        self._stat_running = StatCard('上架中',  _C_BRAND,   self)

        for card in [self._stat_total, self._stat_done,
                     self._stat_failed, self._stat_running]:
            row.addWidget(card)

        self._layout.addLayout(row)

    # ── 进度卡片 ────────────────────────────────────────────────────────────

    def _build_progress_card(self):
        self._prog_card = SimpleCardWidget(self)
        vbox = QVBoxLayout(self._prog_card)
        vbox.setContentsMargins(20, 14, 20, 14)
        vbox.setSpacing(8)

        # 商品名 + 进度计数
        top = QHBoxLayout()
        self._lbl_product = BodyLabel('待机中  ·  导入商品数据后点击「开始上架」', self)
        self._lbl_product.setStyleSheet(f'color: {_C_MUTED}; font-size: 13px;')
        self._lbl_count = CaptionLabel('', self)
        self._lbl_count.setStyleSheet(f'color: {_C_MUTED};')
        top.addWidget(self._lbl_product)
        top.addStretch()
        top.addWidget(self._lbl_count)

        # 进度条
        self._prog_bar = ProgressBar(self)
        self._prog_bar.setValue(0)
        self._prog_bar.setFixedHeight(4)

        # 步骤胶囊
        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)
        self._pills: list[StepPill] = []
        for name in _STEPS:
            pill = StepPill(name, self)
            self._pills.append(pill)
            pills_row.addWidget(pill)
        pills_row.addStretch()

        vbox.addLayout(top)
        vbox.addWidget(self._prog_bar)
        vbox.addLayout(pills_row)

        self._layout.addWidget(self._prog_card)

    # ── 拆分区域（表格 + 日志）──────────────────────────────────────────────

    def _build_split_area(self):
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet(
            'QSplitter::handle { background: rgba(0,0,0,0.06); }'
            'QSplitter::handle:hover { background: rgba(79,110,247,0.25); }'
        )

        # 任务列表
        table_wrap = SimpleCardWidget(self)
        tw_layout = QVBoxLayout(table_wrap)
        tw_layout.setContentsMargins(0, 0, 0, 0)
        tw_layout.setSpacing(0)

        # 表格标题行
        hdr = QHBoxLayout()
        hdr.setContentsMargins(16, 10, 16, 8)
        lbl = StrongBodyLabel('任务列表', self)
        hdr.addWidget(lbl)
        hdr.addStretch()
        tw_layout.addLayout(hdr)

        self._table = TaskTable(self)
        tw_layout.addWidget(self._table)

        # 日志面板
        log_wrap = SimpleCardWidget(self)
        lw_layout = QVBoxLayout(log_wrap)
        lw_layout.setContentsMargins(0, 0, 0, 0)
        lw_layout.setSpacing(0)

        log_hdr = QHBoxLayout()
        log_hdr.setContentsMargins(16, 8, 16, 6)
        log_lbl = StrongBodyLabel('运行日志', self)
        log_hdr.addWidget(log_lbl)
        log_hdr.addStretch()
        clear_btn = TransparentPushButton('清空', self)
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear_log)
        log_hdr.addWidget(clear_btn)
        lw_layout.addLayout(log_hdr)

        self._log = LogWidget(self)
        lw_layout.addWidget(self._log)

        splitter.addWidget(table_wrap)
        splitter.addWidget(log_wrap)
        splitter.setSizes([420, 180])

        self._layout.addWidget(splitter)

    def _clear_log(self):
        self._log.clear()

    # ── 外部接口 ────────────────────────────────────────────────────────────

    def set_browser_status(self, connected: bool):
        if connected:
            self._browser_badge.setText('● 已连接')
            self._browser_badge.setStyleSheet(f'color: {_C_SUCCESS}; font-size: 12px; padding: 0 8px;')
        else:
            self._browser_badge.setText('● 未连接')
            self._browser_badge.setStyleSheet(f'color: {_C_MUTED}; font-size: 12px; padding: 0 8px;')

    def load_products(self, products, folder_name: str = ''):
        self._table.load(products)
        self.refresh_stats(products)
        self._btn_start.setEnabled(True)
        if folder_name:
            self._lbl_product.setText(f'已加载 {len(products)} 个商品  ·  {folder_name}')
            self._lbl_product.setStyleSheet(f'color: {_C_TEXT}; font-size: 13px;')

    def refresh_stats(self, products):
        total   = len(products)
        done    = sum(1 for p in products if p.status == TaskStatus.DONE)
        failed  = sum(1 for p in products if p.status == TaskStatus.FAILED)
        running = sum(1 for p in products if p.status == TaskStatus.RUNNING)
        self._stat_total.set_value(total)
        self._stat_done.set_value(done)
        self._stat_failed.set_value(failed)
        self._stat_running.set_value(running)
        if total:
            self._prog_bar.setValue(int(done / total * 100))

    def update_product(self, product):
        self._table.update_product(product)

    def update_step(self, seq: str, step_text: str, products):
        self._table.update_step(seq, step_text)

        product = next((p for p in products if str(p.seq) == str(seq)), None)
        if product:
            short = (product.title[:42] + '…') if len(product.title) > 42 else product.title
            self._lbl_product.setText(f'正在上架：{short}')
            self._lbl_product.setStyleSheet(f'color: {_C_TEXT}; font-size: 13px;')
            done  = sum(1 for p in products if p.status == TaskStatus.DONE)
            total = len(products)
            self._lbl_count.setText(f'{done} / {total}')

        idx = next((i for i, s in enumerate(_STEPS) if step_text.startswith(s)), -1)
        for i, pill in enumerate(self._pills):
            if i < idx:
                pill.set_done()
            elif i == idx:
                pill.set_active(step_text[:8] if step_text else None)
            else:
                pill.reset()

    def reset_progress(self):
        self._lbl_product.setText('上架完成 · 所有任务已处理')
        self._lbl_product.setStyleSheet(f'color: {_C_SUCCESS}; font-size: 13px;')
        self._lbl_count.setText('')
        for pill in self._pills:
            pill.reset()

    def append_log(self, time_str: str, level: str, msg: str):
        self._log.append_line(time_str, level, msg)

    def set_running(self, running: bool):
        self._btn_import.setEnabled(not running)
        self._btn_start.setEnabled(not running)
        self._btn_pause.setEnabled(running)
        self._btn_stop.setEnabled(running)

    def set_paused(self, paused: bool):
        self._btn_pause.setText('继续' if paused else '暂停')

    def set_retry_enabled(self, enabled: bool):
        self._btn_retry.setEnabled(enabled)
