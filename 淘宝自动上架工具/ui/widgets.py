"""共享 UI 组件"""
import tkinter as tk
from ui.styles import hover_color, BORDER, BG_CARD, TEXT_MUTED


def flat_btn(parent, text, bg, fg='#FFFFFF', cmd=None, state='normal',
             padx=14, pady=7, font=None, width=None):
    """扁平风格按钮，带悬停变色效果"""
    if font is None:
        font = ('Microsoft YaHei UI', 10)
    h_bg = hover_color(bg)
    kw = dict(text=text, font=font, bg=bg, fg=fg, relief='flat', bd=0,
              activebackground=h_bg, activeforeground=fg,
              padx=padx, pady=pady, cursor='hand2',
              command=cmd, state=state)
    if width is not None:
        kw['width'] = width
    btn = tk.Button(parent, **kw)

    def _enter(e):
        if str(btn['state']) != 'disabled':
            btn.configure(bg=h_bg)

    def _leave(e):
        if str(btn['state']) != 'disabled':
            btn.configure(bg=bg)

    btn.bind('<Enter>', _enter)
    btn.bind('<Leave>', _leave)
    return btn


def ghost_btn(parent, text, cmd=None, state='normal', font=None):
    """边框幽灵按钮"""
    if font is None:
        font = ('Microsoft YaHei UI', 10)
    frm = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    btn = tk.Button(frm, text=text, font=font,
                    bg=BG_CARD, fg=TEXT_MUTED, relief='flat', bd=0,
                    activebackground='#F1F5F9', activeforeground='#334155',
                    padx=12, pady=6, cursor='hand2',
                    command=cmd, state=state)
    btn.pack()

    def _enter(e):
        if str(btn['state']) != 'disabled':
            btn.configure(bg='#F1F5F9')

    def _leave(e):
        if str(btn['state']) != 'disabled':
            btn.configure(bg=BG_CARD)

    btn.bind('<Enter>', _enter)
    btn.bind('<Leave>', _leave)
    frm._btn = btn  # expose inner button for state changes
    return frm


class Divider(tk.Frame):
    """分隔线"""
    def __init__(self, parent, orient='h', color=BORDER, **kw):
        if orient == 'h':
            super().__init__(parent, bg=color, height=1, **kw)
        else:
            super().__init__(parent, bg=color, width=1, **kw)
