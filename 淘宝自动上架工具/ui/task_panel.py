"""任务列表面板"""
import tkinter as tk
from tkinter import ttk
from ui.styles import (BG_CARD, BG_MAIN, BG_HOVER, BORDER, BORDER_MID,
                       PRIMARY, PRIMARY_LIGHT, SUCCESS, DANGER, WARNING, MUTED,
                       TEXT_H, TEXT_BODY, TEXT_MUTED, TEXT_HINT,
                       STATUS_COLOR, STATUS_LABEL)

_FONT = ('Microsoft YaHei UI', 10)
_FONT_B = ('Microsoft YaHei UI', 10, 'bold')
_FONT_S = ('Microsoft YaHei UI', 9)


class TaskPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=BG_CARD, **kw)
        self._rows: dict[str, str] = {}
        self._build()

    def _build(self):
        # ── 统计条（单行内联，无卡片）────────────────────────────────────
        bar = tk.Frame(self, bg=BG_CARD, height=40)
        bar.pack(fill='x')
        bar.pack_propagate(False)

        # 左侧标题
        tk.Label(bar, text='任务列表', font=('Microsoft YaHei UI', 10, 'bold'),
                 bg=BG_CARD, fg=TEXT_H).pack(side='left', padx=(14, 20), pady=10)

        # 内联统计项
        def _stat(label, color):
            tk.Label(bar, text=label, font=_FONT_S,
                     bg=BG_CARD, fg=TEXT_MUTED).pack(side='left', pady=10)
            lbl = tk.Label(bar, text='0', font=_FONT_B,
                           bg=BG_CARD, fg=color, padx=4)
            lbl.pack(side='left', pady=10)
            return lbl

        self._lbl_total   = _stat('总数', TEXT_H)
        tk.Label(bar, text='·', font=_FONT_S, bg=BG_CARD, fg=BORDER_MID).pack(side='left')
        self._lbl_done    = _stat('完成', SUCCESS)
        tk.Label(bar, text='·', font=_FONT_S, bg=BG_CARD, fg=BORDER_MID).pack(side='left')
        self._lbl_failed  = _stat('失败', DANGER)
        tk.Label(bar, text='·', font=_FONT_S, bg=BG_CARD, fg=BORDER_MID).pack(side='left')
        self._lbl_pending = _stat('待处理', WARNING)

        # ── 分隔线 ────────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x')

        # ── 表格区域 ──────────────────────────────────────────────────────
        table_wrap = tk.Frame(self, bg=BG_CARD)
        table_wrap.pack(fill='both', expand=True)

        self._setup_style()

        cols    = ('seq', 'title', 'skus', 'status', 'item_id', 'error')
        headers = ('序号', '商品标题', 'SKU', '状态', '商品 ID', '备注')
        widths  = (52,     340,       48,    90,      130,       220)
        anchors = ('center','w',      'center','center','center','w')

        self._tree = ttk.Treeview(table_wrap, columns=cols, show='headings',
                                   selectmode='browse', height=18,
                                   style='T.Treeview')
        for col, hdr, w, anc in zip(cols, headers, widths, anchors):
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, minwidth=36, anchor=anc)

        vsb = ttk.Scrollbar(table_wrap, orient='vertical',   command=self._tree.yview)
        hsb = ttk.Scrollbar(table_wrap, orient='horizontal', command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        # 行颜色标签
        self._tree.tag_configure('DONE',    background='#F0FDF4', foreground='#065F46')
        self._tree.tag_configure('FAILED',  background='#FEF2F2', foreground='#991B1B')
        self._tree.tag_configure('RUNNING', background=PRIMARY_LIGHT, foreground=PRIMARY)
        self._tree.tag_configure('PENDING', background=BG_CARD, foreground=TEXT_BODY)
        self._tree.tag_configure('SKIPPED', background=BG_HOVER, foreground=TEXT_MUTED)

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        style.configure('T.Treeview',
                        background=BG_CARD,
                        foreground=TEXT_BODY,
                        fieldbackground=BG_CARD,
                        rowheight=32,
                        font=('Microsoft YaHei UI', 10),
                        borderwidth=0,
                        relief='flat')
        style.configure('T.Treeview.Heading',
                        background=BG_MAIN,
                        foreground=TEXT_MUTED,
                        font=('Microsoft YaHei UI', 9, 'bold'),
                        borderwidth=0,
                        relief='flat',
                        padding=(8, 6))
        style.map('T.Treeview',
                  background=[('selected', PRIMARY_LIGHT)],
                  foreground=[('selected', TEXT_H)])
        style.map('T.Treeview.Heading',
                  background=[('active', BG_HOVER)])

        # 细滚动条（无箭头）
        for orient in ('Vertical', 'Horizontal'):
            style.layout(f'{orient}.TScrollbar', [
                (f'{orient}.TScrollbar.trough', {
                    'children': [(f'{orient}.TScrollbar.thumb',
                                  {'expand': '1', 'sticky': 'nswe'})],
                    'sticky': 'nsew',
                })
            ])
        style.configure('Vertical.TScrollbar',
                        background='#D1D5DB', troughcolor=BG_MAIN,
                        borderwidth=0, relief='flat', width=6)
        style.configure('Horizontal.TScrollbar',
                        background='#D1D5DB', troughcolor=BG_MAIN,
                        borderwidth=0, relief='flat', width=6)
        style.map('Vertical.TScrollbar',
                  background=[('active', '#9CA3AF')])
        style.map('Horizontal.TScrollbar',
                  background=[('active', '#9CA3AF')])

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def load_products(self, products):
        self._tree.delete(*self._tree.get_children())
        self._rows.clear()
        for p in products:
            status_text = STATUS_LABEL.get(p.status.name, p.status.name)
            iid = self._tree.insert('', 'end',
                values=(p.seq, p.title, len(p.skus), status_text,
                        p.item_id, p.error),
                tags=(p.status.name,))
            self._rows[p.seq] = iid
        self._refresh_stats(products)

    def update_product(self, product):
        iid = self._rows.get(product.seq)
        if not iid:
            return
        status_text = STATUS_LABEL.get(product.status.name, product.status.name)
        self._tree.item(iid,
            values=(product.seq, product.title, len(product.skus),
                    status_text, product.item_id, product.error),
            tags=(product.status.name,))

    def update_step(self, seq: str, step_text: str):
        iid = self._rows.get(seq)
        if not iid:
            return
        vals = list(self._tree.item(iid, 'values'))
        if len(vals) >= 4:
            vals[3] = step_text
            self._tree.item(iid, values=vals, tags=('RUNNING',))

    def _refresh_stats(self, products):
        from models.product import TaskStatus
        total   = len(products)
        done    = sum(1 for p in products if p.status == TaskStatus.DONE)
        failed  = sum(1 for p in products if p.status == TaskStatus.FAILED)
        pending = sum(1 for p in products if p.status == TaskStatus.PENDING)
        self._lbl_total.configure(text=str(total))
        self._lbl_done.configure(text=str(done))
        self._lbl_failed.configure(text=str(failed))
        self._lbl_pending.configure(text=str(pending))
