"""设计令牌 — 极简淡雅单色调系统"""

# ── 主色 (淡紫) ───────────────────────────────────────────────
PRIMARY       = '#A78BFA'   # 紫罗兰 400 (更浅)
PRIMARY_HOVER = '#8B5CF6'   # 紫罗兰 500 (悬停)
PRIMARY_LIGHT = '#F5F3FF'   # 紫罗兰 50  (浅底)
PRIMARY_DARK  = '#7C3AED'   # 紫罗兰 600
ACCENT        = '#A78BFA'   # 同主色

SUCCESS       = '#059669'   # 翠绿
SUCCESS_LIGHT = '#ECFDF5'
DANGER        = '#DC2626'   # 红
DANGER_LIGHT  = '#FEF2F2'
WARNING       = '#D97706'   # 琥珀
WARNING_LIGHT = '#FFFBEB'
MUTED         = '#9CA3AF'   # 灰 400

# ── 背景层次 ──────────────────────────────────────────────────
BG_MAIN       = '#F3F4F6'   # 页面底 (灰 100)
BG_CARD       = '#FFFFFF'   # 卡片白
BG_HOVER      = '#F9FAFB'   # 悬停 (灰 50)
BG_SIDEBAR    = '#FAFAFA'   # 侧边栏 (极浅灰)

# ── 文字层次 ──────────────────────────────────────────────────
TEXT_H        = '#111827'   # 标题 (灰 900)
TEXT_BODY     = '#374151'   # 正文 (灰 700)
TEXT_MUTED    = '#6B7280'   # 辅助 (灰 500)
TEXT_HINT     = '#9CA3AF'   # 占位 (灰 400)

# ── 边框 ──────────────────────────────────────────────────────
BORDER        = '#E5E7EB'   # 灰 200
BORDER_MID    = '#D1D5DB'   # 灰 300

# ── 侧边栏专色 (浅色) ─────────────────────────────────────────
SIDEBAR_ITEM       = '#FFFFFF'       # 卡片白
SIDEBAR_TEXT       = '#7C5CBF'       # 紫调正文
SIDEBAR_SUB        = '#A78BFA'       # 淡紫辅助
SIDEBAR_ACCENT     = '#A78BFA'       # 淡紫强调
SIDEBAR_ITEM_BG    = '#F9FAFB'       # 卡片底色

# ── 字体 ──────────────────────────────────────────────────────
_YH         = 'Microsoft YaHei UI'
FONT_TITLE  = (_YH, 14, 'bold')
FONT_LARGE  = (_YH, 12, 'bold')
FONT_NORMAL = (_YH, 11)
FONT_SMALL  = (_YH, 10)
FONT_TINY   = (_YH, 9)
FONT_MONO   = ('Consolas', 10)

# ── 状态映射 ──────────────────────────────────────────────────
STATUS_COLOR = {
    'PENDING':  (WARNING,  WARNING_LIGHT),
    'RUNNING':  (PRIMARY,  PRIMARY_LIGHT),
    'DONE':     (SUCCESS,  SUCCESS_LIGHT),
    'FAILED':   (DANGER,   DANGER_LIGHT),
    'SKIPPED':  (MUTED,    '#F9FAFB'),
}
STATUS_LABEL = {
    'PENDING': '待上架',
    'RUNNING': '上架中',
    'DONE':    '已完成',
    'FAILED':  '失败',
    'SKIPPED': '已跳过',
}

# ── 工具 ──────────────────────────────────────────────────────
def hover_color(hex_color: str, factor: float = 0.10) -> str:
    c = hex_color.lstrip('#')
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return '#{:02X}{:02X}{:02X}'.format(
        max(0, int(r * (1 - factor))),
        max(0, int(g * (1 - factor))),
        max(0, int(b * (1 - factor))),
    )
