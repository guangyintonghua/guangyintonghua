"""账号状态面板（侧边栏内嵌，浅色主题）"""
import tkinter as tk
from ui.styles import (BG_SIDEBAR, SIDEBAR_ITEM_BG, SIDEBAR_TEXT, SIDEBAR_SUB,
                       SIDEBAR_ACCENT, SUCCESS, DANGER, BORDER,
                       TEXT_MUTED, PRIMARY_LIGHT, FONT_SMALL, FONT_TINY)


class AccountPanel(tk.Frame):
    def __init__(self, master, account_manager, **kw):
        super().__init__(master, bg=BG_SIDEBAR, **kw)
        self._am = account_manager
        self._cards: list[dict] = []
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_SIDEBAR)
        hdr.pack(fill='x', padx=16, pady=(20, 8))
        tk.Label(hdr, text='账号',
                 font=('Microsoft YaHei UI', 9, 'bold'),
                 bg=BG_SIDEBAR, fg=SIDEBAR_ACCENT).pack(anchor='w')

        self._container = tk.Frame(self, bg=BG_SIDEBAR)
        self._container.pack(fill='x', padx=10)
        self.refresh()

    def refresh(self):
        for w in self._container.winfo_children():
            w.destroy()
        self._cards.clear()
        for info in self._am.status():
            self._make_card(info)

    def _make_card(self, info: dict):
        available = info.get('available', True)
        today     = info.get('today', 0)
        limit     = info.get('limit', 200)
        name      = info.get('name', '—')

        # 外框 (边框模拟)
        outer = tk.Frame(self._container, bg=BORDER, padx=1, pady=1)
        outer.pack(fill='x', pady=3)

        card = tk.Frame(outer, bg=SIDEBAR_ITEM_BG, padx=12, pady=10)
        card.pack(fill='both')

        # 账号名行
        name_row = tk.Frame(card, bg=SIDEBAR_ITEM_BG)
        name_row.pack(fill='x')

        dot_color = SUCCESS if available else DANGER
        tk.Label(name_row, text='●', font=('Microsoft YaHei UI', 7),
                 bg=SIDEBAR_ITEM_BG, fg=dot_color).pack(side='left', padx=(0, 6))
        tk.Label(name_row, text=name,
                 font=('Microsoft YaHei UI', 10, 'bold'),
                 bg=SIDEBAR_ITEM_BG, fg=SIDEBAR_TEXT).pack(side='left')

        # 进度行
        prog_row = tk.Frame(card, bg=SIDEBAR_ITEM_BG)
        prog_row.pack(fill='x', pady=(6, 0))

        tk.Label(prog_row, text='今日',
                 font=('Microsoft YaHei UI', 9),
                 bg=SIDEBAR_ITEM_BG, fg='#9CA3AF').pack(side='left')

        count_fg = SIDEBAR_ACCENT if available else DANGER
        tk.Label(prog_row, text=f'{today} / {limit}',
                 font=('Microsoft YaHei UI', 9, 'bold'),
                 bg=SIDEBAR_ITEM_BG, fg=count_fg).pack(side='right')

        # 进度条底轨
        bar_bg = tk.Frame(card, bg=BORDER, height=3)
        bar_bg.pack(fill='x', pady=(5, 0))
        bar_bg.pack_propagate(False)

        ratio = min(today / limit, 1.0) if limit > 0 else 0
        if ratio > 0:
            fill_color = SIDEBAR_ACCENT if available else DANGER
            bar_fill = tk.Frame(bar_bg, bg=fill_color, height=3)
            bar_fill.place(relx=0, rely=0, relwidth=ratio, relheight=1)
