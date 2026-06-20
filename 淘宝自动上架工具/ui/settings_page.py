# -*- coding: utf-8 -*-
"""设置页面"""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import (
    ScrollArea, SimpleCardWidget, StrongBodyLabel, BodyLabel,
    LineEdit, PrimaryPushButton, FluentIcon as FIF,
    InfoBar, InfoBarPosition, SpinBox, CaptionLabel,
)

_CFG = Path('config/settings.json')


def _load() -> dict:
    if _CFG.exists():
        try:
            return json.loads(_CFG.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def _save(data: dict):
    _CFG.parent.mkdir(parents=True, exist_ok=True)
    _CFG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class SettingsPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('settingsPage')
        self.setWidgetResizable(True)

        container = QWidget(self)
        self.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        cfg = _load()

        # ── 浏览器连接 ──────────────────────────────────────────────────────
        browser_card = SimpleCardWidget(self)
        bc = QVBoxLayout(browser_card)
        bc.setContentsMargins(20, 16, 20, 16)
        bc.setSpacing(12)
        bc.addWidget(StrongBodyLabel('浏览器连接', self))

        port_row = QHBoxLayout()
        port_row.addWidget(BodyLabel('CDP 调试端口', self))
        port_row.addStretch()
        self._port = SpinBox(self)
        self._port.setRange(1024, 65535)
        self._port.setValue(cfg.get('debug_port', 9222))
        self._port.setFixedWidth(100)
        port_row.addWidget(self._port)
        bc.addLayout(port_row)

        layout.addWidget(browser_card)

        # ── 上架配置 ────────────────────────────────────────────────────────
        upload_card = SimpleCardWidget(self)
        uc = QVBoxLayout(upload_card)
        uc.setContentsMargins(20, 16, 20, 16)
        uc.setSpacing(12)
        uc.addWidget(StrongBodyLabel('上架配置', self))

        tpl_row = QHBoxLayout()
        tpl_row.addWidget(BodyLabel('运费模板名称', self))
        tpl_row.addStretch()
        self._tpl = LineEdit(self)
        self._tpl.setText(cfg.get('shipping_tpl', '光阴童话'))
        self._tpl.setFixedWidth(200)
        tpl_row.addWidget(self._tpl)
        uc.addLayout(tpl_row)

        folder_row = QHBoxLayout()
        folder_row.addWidget(BodyLabel('默认商品文件夹', self))
        folder_row.addStretch()
        self._folder = LineEdit(self)
        self._folder.setText(cfg.get('default_folder', ''))
        self._folder.setMinimumWidth(300)
        self._folder.setPlaceholderText('留空则每次手动导入')
        folder_row.addWidget(self._folder)
        uc.addLayout(folder_row)

        layout.addWidget(upload_card)

        # ── 保存按钮 ────────────────────────────────────────────────────────
        save_btn = PrimaryPushButton(FIF.SAVE, '保存设置', self)
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)
        layout.addStretch()

    def _save(self):
        data = _load()
        data['debug_port']     = self._port.value()
        data['shipping_tpl']   = self._tpl.text().strip()
        data['default_folder'] = self._folder.text().strip()
        try:
            _save(data)
            InfoBar.success('已保存', '设置已保存，重启后生效', parent=self.window(),
                            position=InfoBarPosition.TOP_RIGHT, duration=2000)
        except Exception as e:
            InfoBar.error('保存失败', str(e), parent=self.window(),
                          position=InfoBarPosition.TOP_RIGHT, duration=4000)
