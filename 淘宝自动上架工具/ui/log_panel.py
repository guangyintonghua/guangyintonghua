"""实时日志面板 — 浅色主题"""
import tkinter as tk
from tkinter import ttk
from ui.styles import (BG_CARD, BG_MAIN, BORDER, TEXT_MUTED,
                       TEXT_BODY, TEXT_H, SUCCESS, DANGER, WARNING,
                       PRIMARY, MUTED)

# 日志区底色：极浅暖灰，比白色多一点质感
_LOG_BG   = '#F8F9FB'
_LOG_TIME = '#9CA3AF'
_LOG_SEP  = '#E5E7EB'


class LogPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=BG_CARD, **kw)
        self._build()

    def _build(self):
        # 面板头部
        header = tk.Frame(self, bg=BG_CARD, height=38)
        header.pack(fill='x')
        header.pack_propagate(False)

        # 左侧标题
        left = tk.Frame(header, bg=BG_CARD)
        left.pack(side='left', fill='y')
        tk.Label(left, text='运行日志',
                 font=('Microsoft YaHei UI', 10, 'bold'),
                 bg=BG_CARD, fg=TEXT_H).pack(side='left', padx=(14, 0), pady=10)
        tk.Label(left, text='实时输出',
                 font=('Microsoft YaHei UI', 9),
                 bg=BG_CARD, fg='#9CA3AF').pack(side='left', padx=6, pady=10)

        # 右侧清空按钮
        clear_btn = tk.Button(header, text='清空',
                              font=('Microsoft YaHei UI', 9),
                              bg=BG_CARD, fg=TEXT_MUTED, relief='flat', bd=0,
                              activebackground=BG_MAIN, activeforeground=TEXT_BODY,
                              padx=10, pady=4, cursor='hand2',
                              command=self.clear)
        clear_btn.pack(side='right', padx=12, pady=8)
        clear_btn.bind('<Enter>', lambda e: clear_btn.configure(bg=BG_MAIN))
        clear_btn.bind('<Leave>', lambda e: clear_btn.configure(bg=BG_CARD))

        # 顶部边框线
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x')

        # 日志文本区
        text_frame = tk.Frame(self, bg=_LOG_BG)
        text_frame.pack(fill='both', expand=True)

        self._text = tk.Text(text_frame,
                             font=('Consolas', 10),
                             bg=_LOG_BG, fg=TEXT_BODY,
                             relief='flat', wrap='word', state='disabled',
                             selectbackground='#DBEAFE',
                             selectforeground=TEXT_H,
                             insertbackground=TEXT_MUTED,
                             padx=14, pady=10,
                             spacing1=1, spacing3=3)
        self._text.pack(side='left', fill='both', expand=True)

        # 细滚动条（无箭头，与 task_panel 共用同一 ttk style）
        sb = ttk.Scrollbar(text_frame, orient='vertical', command=self._text.yview)
        sb.pack(side='right', fill='y')
        self._text.configure(yscrollcommand=sb.set)

        # 确保日志面板也应用现代滚动条样式
        _s = ttk.Style()
        _s.configure('Vertical.TScrollbar',
                     background='#D1D5DB', troughcolor=_LOG_BG,
                     borderwidth=0, relief='flat', width=6)

        # 颜色标签 (浅底上的深色字，确保可读)
        self._text.tag_configure('TIME',    foreground=_LOG_TIME)
        self._text.tag_configure('SEP',     foreground=_LOG_SEP)
        self._text.tag_configure('DEBUG',   foreground='#9CA3AF')
        self._text.tag_configure('INFO',    foreground='#374151')
        self._text.tag_configure('SUCCESS', foreground='#047857')   # 深绿
        self._text.tag_configure('WARNING', foreground='#92400E')   # 深琥珀
        self._text.tag_configure('ERROR',   foreground='#B91C1C')   # 深红

    def append(self, time_str: str, level: str, message: str):
        if '成功' in message or 'SUCCESS' in message.upper():
            tag = 'SUCCESS'
        elif level in ('ERROR', 'CRITICAL'):
            tag = 'ERROR'
        elif level == 'WARNING':
            tag = 'WARNING'
        elif level == 'DEBUG':
            tag = 'DEBUG'
        else:
            tag = 'INFO'

        self._text.configure(state='normal')
        self._text.insert('end', f'{time_str}  ', 'TIME')
        self._text.insert('end', f'{message}\n', tag)
        self._text.see('end')
        self._text.configure(state='disabled')

        lines = int(self._text.index('end-1c').split('.')[0])
        if lines > 2000:
            self._text.configure(state='normal')
            self._text.delete('1.0', f'{lines - 2000}.0')
            self._text.configure(state='disabled')

    def clear(self):
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')
        self._text.configure(state='disabled')
