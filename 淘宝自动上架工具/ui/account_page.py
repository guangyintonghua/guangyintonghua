# -*- coding: utf-8 -*-
"""账号管理页面"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import (
    ScrollArea, SimpleCardWidget, StrongBodyLabel, BodyLabel,
    CaptionLabel, PrimaryPushButton, PushButton, FluentIcon as FIF,
    InfoBar, InfoBarPosition,
)


class AccountCard(SimpleCardWidget):
    def __init__(self, name: str, connected: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        dot = QLabel('●', self)
        dot.setFixedWidth(14)
        dot.setStyleSheet(f'color: {"#4ADE80" if connected else "#6B7280"}; font-size: 14px;')

        name_lbl = BodyLabel(name, self)
        status_lbl = CaptionLabel('已连接' if connected else '未连接', self)
        status_lbl.setStyleSheet(f'color: {"#4ADE80" if connected else "#9CA3AF"};')

        layout.addWidget(dot)
        layout.addWidget(name_lbl)
        layout.addStretch()
        layout.addWidget(status_lbl)


class AccountPage(ScrollArea):
    def __init__(self, account_manager, parent=None):
        super().__init__(parent)
        self._am = account_manager
        self.setObjectName('accountPage')
        self.setWidgetResizable(True)

        container = QWidget(self)
        self.setWidget(container)
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(12)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        hdr = QHBoxLayout()
        hdr.addWidget(StrongBodyLabel('账号列表', self))
        hdr.addStretch()
        btn = PrimaryPushButton(FIF.SYNC, '刷新状态', self)
        btn.setFixedHeight(32)
        btn.clicked.connect(self.refresh)
        hdr.addWidget(btn)
        self._layout.addLayout(hdr)

        self._cards_container = QWidget(self)
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._layout.addWidget(self._cards_container)
        self._layout.addStretch()

        self.refresh()

    def refresh(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            accounts = self._am.list_accounts() if hasattr(self._am, 'list_accounts') else []
        except Exception:
            accounts = []

        if not accounts:
            tip = CaptionLabel('暂无账号配置  ·  请在 config/accounts.json 中添加', self)
            tip.setStyleSheet('color: rgba(255,255,255,0.3); padding: 20px 0;')
            self._cards_layout.addWidget(tip)
            return

        for acc in accounts:
            name      = acc if isinstance(acc, str) else acc.get('name', str(acc))
            connected = False
            self._cards_layout.addWidget(AccountCard(name, connected, self))
