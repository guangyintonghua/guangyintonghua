"""
简约淡雅风格 QSS 样式表
主色调：柔和蓝+暖白+浅灰
"""

PALETTE = {
    "bg": "#F5F7FA",
    "card": "#FFFFFF",
    "sidebar": "#FFFFFF",
    "primary": "#4B7BEC",
    "primary_hover": "#3867D6",
    "primary_light": "#EBF0FF",
    "success": "#52B788",
    "success_light": "#E8F5EF",
    "warning": "#F4A261",
    "warning_light": "#FEF3E8",
    "danger": "#E07A7A",
    "danger_light": "#FDEDED",
    "text_primary": "#2D3436",
    "text_secondary": "#636E72",
    "text_hint": "#B2BEC3",
    "border": "#E8ECF0",
    "divider": "#F0F3F7",
    "shadow": "rgba(0,0,0,0.06)",
}

MAIN_QSS = f"""
/* 全局 */
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
    color: {PALETTE['text_primary']};
    background-color: {PALETTE['bg']};
}}

/* 主窗口 */
QMainWindow {{
    background-color: {PALETTE['bg']};
}}

/* 侧边栏 */
#sidebar {{
    background-color: {PALETTE['sidebar']};
    border-right: 1px solid {PALETTE['border']};
    min-width: 200px;
    max-width: 200px;
}}

#sidebar_title {{
    font-size: 16px;
    font-weight: bold;
    color: {PALETTE['primary']};
    padding: 24px 16px 8px 16px;
}}

#sidebar_subtitle {{
    font-size: 11px;
    color: {PALETTE['text_hint']};
    padding: 0 16px 16px 16px;
}}

/* 侧边栏导航按钮 */
#nav_btn {{
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: {PALETTE['text_secondary']};
    font-size: 14px;
    margin: 2px 8px;
}}
#nav_btn:hover {{
    background-color: {PALETTE['primary_light']};
    color: {PALETTE['primary']};
}}
#nav_btn[active="true"] {{
    background-color: {PALETTE['primary_light']};
    color: {PALETTE['primary']};
    font-weight: bold;
}}

/* 卡片 */
#card {{
    background-color: {PALETTE['card']};
    border-radius: 12px;
    border: 1px solid {PALETTE['border']};
}}

/* 主按钮 */
QPushButton#btn_primary {{
    background-color: {PALETTE['primary']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
}}
QPushButton#btn_primary:hover {{
    background-color: {PALETTE['primary_hover']};
}}
QPushButton#btn_primary:disabled {{
    background-color: {PALETTE['text_hint']};
}}

/* 次要按钮 */
QPushButton#btn_secondary {{
    background-color: transparent;
    color: {PALETTE['primary']};
    border: 1.5px solid {PALETTE['primary']};
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 14px;
}}
QPushButton#btn_secondary:hover {{
    background-color: {PALETTE['primary_light']};
}}

/* 危险按钮 */
QPushButton#btn_danger {{
    background-color: transparent;
    color: {PALETTE['danger']};
    border: 1.5px solid {PALETTE['danger']};
    border-radius: 8px;
    padding: 9px 20px;
}}

/* 输入框 */
QLineEdit, QTextEdit, QPlainTextEdit {{
    border: 1.5px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 8px 12px;
    background-color: {PALETTE['card']};
    color: {PALETTE['text_primary']};
    selection-background-color: {PALETTE['primary_light']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {PALETTE['primary']};
}}

/* 下拉框 */
QComboBox {{
    border: 1.5px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 8px 12px;
    background-color: {PALETTE['card']};
    color: {PALETTE['text_primary']};
    min-width: 120px;
}}
QComboBox:focus {{
    border-color: {PALETTE['primary']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    background-color: {PALETTE['card']};
    selection-background-color: {PALETTE['primary_light']};
    selection-color: {PALETTE['primary']};
}}

/* 滑块 */
QSlider::groove:horizontal {{
    height: 4px;
    background: {PALETTE['border']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {PALETTE['primary']};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {PALETTE['primary']};
    border-radius: 2px;
}}

/* 数值框 */
QSpinBox {{
    border: 1.5px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 6px 10px;
    background: {PALETTE['card']};
}}
QSpinBox:focus {{
    border-color: {PALETTE['primary']};
}}

/* 表格 */
QTableWidget {{
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    background-color: {PALETTE['card']};
    gridline-color: {PALETTE['divider']};
}}
QTableWidget::item {{
    padding: 8px 12px;
    border-bottom: 1px solid {PALETTE['divider']};
}}
QTableWidget::item:selected {{
    background-color: {PALETTE['primary_light']};
    color: {PALETTE['primary']};
}}
QHeaderView::section {{
    background-color: {PALETTE['bg']};
    border: none;
    border-bottom: 1px solid {PALETTE['border']};
    padding: 10px 12px;
    font-weight: bold;
    color: {PALETTE['text_secondary']};
    font-size: 13px;
}}

/* 列表 */
QListWidget {{
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    background-color: {PALETTE['card']};
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background-color: {PALETTE['primary_light']};
    color: {PALETTE['primary']};
}}
QListWidget::item:hover {{
    background-color: {PALETTE['bg']};
}}

/* 复选框 */
QCheckBox {{
    spacing: 8px;
    color: {PALETTE['text_primary']};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {PALETTE['border']};
    border-radius: 4px;
    background: white;
}}
QCheckBox::indicator:checked {{
    border-color: {PALETTE['primary']};
    background-color: {PALETTE['primary']};
}}

/* 标签 */
QLabel#label_title {{
    font-size: 22px;
    font-weight: bold;
    color: {PALETTE['text_primary']};
}}
QLabel#label_section {{
    font-size: 16px;
    font-weight: bold;
    color: {PALETTE['text_primary']};
}}
QLabel#label_hint {{
    font-size: 12px;
    color: {PALETTE['text_hint']};
}}
QLabel#tag_success {{
    background-color: {PALETTE['success_light']};
    color: {PALETTE['success']};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: bold;
}}
QLabel#tag_warning {{
    background-color: {PALETTE['warning_light']};
    color: {PALETTE['warning']};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: bold;
}}
QLabel#tag_danger {{
    background-color: {PALETTE['danger_light']};
    color: {PALETTE['danger']};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: bold;
}}

/* 进度条 */
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {PALETTE['border']};
    text-align: center;
    height: 8px;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background-color: {PALETTE['primary']};
    border-radius: 4px;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE['border']};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PALETTE['text_hint']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {PALETTE['border']};
    border-radius: 3px;
}}

/* 分隔线 */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {PALETTE['border']};
}}

/* 标签页 */
QTabWidget::pane {{
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    background: {PALETTE['card']};
}}
QTabBar::tab {{
    padding: 8px 20px;
    border: none;
    color: {PALETTE['text_secondary']};
    background: transparent;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {PALETTE['primary']};
    border-bottom: 2px solid {PALETTE['primary']};
    font-weight: bold;
}}
"""
