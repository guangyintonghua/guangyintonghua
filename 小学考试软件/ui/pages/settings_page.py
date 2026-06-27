from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QFormLayout, QMessageBox,
    QScrollArea, QListWidget, QListWidgetItem, QDialog,
    QDialogButtonBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

import config
from data import database as db
from data.regions import REGIONS, TEXTBOOKS
from core.knowledge_map import GRADES
from core import tts_engine
from ui.styles import PALETTE


class AddStudentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加学生")
        self.setFixedSize(360, 200)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 16)

        form = QFormLayout()
        form.setSpacing(12)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例：小明")
        form.addRow("姓名：", self._name_edit)

        self._grade_combo = QComboBox()
        self._grade_combo.addItems(GRADES)
        self._grade_combo.setCurrentText("三年级")
        form.addRow("年级：", self._grade_combo)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self) -> tuple[str, str]:
        return self._name_edit.text().strip(), self._grade_combo.currentText()


class SettingsPage(QWidget):
    student_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(24)

        title = QLabel("设置")
        title.setObjectName("label_title")
        layout.addWidget(title)

        # ── API 配置 ──────────────────────────────
        api_card = self._make_group("🔑  API 配置")
        api_layout = QFormLayout()
        api_layout.setSpacing(12)

        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("sk-xxxxxxxxxxxxxxxx")
        self._key_edit.setText(config.get("api_key") or "")
        self._key_edit.setFixedHeight(38)
        api_layout.addRow("API Key：", self._key_edit)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.deepseek.com")
        self._url_edit.setText(config.get("api_base_url") or "https://api.deepseek.com")
        self._url_edit.setFixedHeight(38)
        api_layout.addRow("API 地址：", self._url_edit)

        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("deepseek-chat")
        self._model_edit.setText(config.get("model_chat") or "deepseek-chat")
        self._model_edit.setFixedHeight(38)
        api_layout.addRow("对话模型：", self._model_edit)

        self._vision_edit = QLineEdit()
        self._vision_edit.setPlaceholderText("deepseek-vl（可选）")
        self._vision_edit.setText(config.get("model_vision") or "")
        self._vision_edit.setFixedHeight(38)
        api_layout.addRow("视觉模型：", self._vision_edit)
        api_card.layout().addLayout(api_layout)

        # 测试 & 保存
        api_btn_row = QHBoxLayout()
        self._test_btn = QPushButton("🔗  测试连接")
        self._test_btn.setObjectName("btn_secondary")
        self._test_btn.clicked.connect(self._test_api)
        api_btn_row.addWidget(self._test_btn)
        self._save_api_btn = QPushButton("保存 API 设置")
        self._save_api_btn.setObjectName("btn_primary")
        self._save_api_btn.clicked.connect(self._save_api)
        api_btn_row.addWidget(self._save_api_btn)
        api_btn_row.addStretch()
        api_card.layout().addLayout(api_btn_row)

        layout.addWidget(api_card)

        # ── 学生管理 ──────────────────────────────
        student_card = self._make_group("👤  学生管理")

        self._student_list = QListWidget()
        self._student_list.setFixedHeight(160)
        self._student_list.itemClicked.connect(self._on_student_select)
        student_card.layout().addWidget(self._student_list)

        student_btn_row = QHBoxLayout()
        add_btn = QPushButton("＋  添加学生")
        add_btn.setObjectName("btn_secondary")
        add_btn.clicked.connect(self._add_student)
        student_btn_row.addWidget(add_btn)

        self._set_default_btn = QPushButton("✓  设为当前学生")
        self._set_default_btn.setObjectName("btn_primary")
        self._set_default_btn.setEnabled(False)
        self._set_default_btn.clicked.connect(self._set_default_student)
        student_btn_row.addWidget(self._set_default_btn)

        self._edit_grade_btn = QPushButton("✏ 修改年级")
        self._edit_grade_btn.setObjectName("btn_secondary")
        self._edit_grade_btn.setEnabled(False)
        self._edit_grade_btn.clicked.connect(self._edit_student_grade)
        student_btn_row.addWidget(self._edit_grade_btn)

        student_btn_row.addStretch()
        student_card.layout().addLayout(student_btn_row)

        self._current_student_lbl = QLabel("")
        self._current_student_lbl.setStyleSheet(
            f"color: {PALETTE['success']}; font-size: 13px; font-weight: bold;"
        )
        student_card.layout().addWidget(self._current_student_lbl)
        layout.addWidget(student_card)

        # ── 教学设置 ──────────────────────────────
        teach_card = self._make_group("📍  教学设置")
        teach_form = QFormLayout()
        teach_form.setSpacing(12)

        self._region_combo = QComboBox()
        self._region_combo.addItems(REGIONS)
        saved_region = config.get("region") or "全国通用"
        if saved_region in REGIONS:
            self._region_combo.setCurrentText(saved_region)
        self._region_combo.setMinimumWidth(220)
        self._region_combo.currentTextChanged.connect(self._save_teaching)
        teach_form.addRow("所在地区：", self._region_combo)

        self._textbook_combo = QComboBox()
        self._textbook_combo.addItems(list(TEXTBOOKS.keys()))
        saved_tb = config.get("textbook_version") or "人教版（PEP）"
        if saved_tb in TEXTBOOKS:
            self._textbook_combo.setCurrentText(saved_tb)
        self._textbook_combo.setMinimumWidth(220)
        self._textbook_combo.currentTextChanged.connect(self._save_teaching)
        teach_form.addRow("教材版本：", self._textbook_combo)

        teach_card.layout().addLayout(teach_form)

        self._teach_hint = QLabel("")
        self._teach_hint.setWordWrap(True)
        self._teach_hint.setStyleSheet(
            f"font-size: 12px; color: {PALETTE['text_secondary']};"
            f"background: {PALETTE['primary_light']}; border-radius: 6px;"
            f"padding: 6px 10px; margin-top: 4px;"
        )
        teach_card.layout().addWidget(self._teach_hint)
        self._refresh_teach_hint()

        layout.addWidget(teach_card)

        # ── 语音设置 ──────────────────────────────
        voice_card = self._make_group("🔊  语音讲解设置")
        voice_form = QFormLayout()
        voice_form.setSpacing(12)

        self._voice_combo = QComboBox()
        for name in tts_engine.VOICES:
            self._voice_combo.addItem(name)
        saved_voice = config.get("tts_voice") or tts_engine.DEFAULT_VOICE
        for i, v in enumerate(tts_engine.VOICES.values()):
            if v == saved_voice:
                self._voice_combo.setCurrentIndex(i)
                break
        self._voice_combo.currentIndexChanged.connect(self._save_voice)
        voice_form.addRow("朗读声音：", self._voice_combo)

        from PyQt6.QtWidgets import QSlider
        from PyQt6.QtCore import Qt as Qt2
        rate_row = QHBoxLayout()
        self._rate_slider = QSlider(Qt2.Orientation.Horizontal)
        self._rate_slider.setRange(-30, 30)
        saved_rate_str = config.get("tts_rate") or "-10%"
        saved_rate = int(saved_rate_str.replace("%", "").replace("+", ""))
        self._rate_slider.setValue(saved_rate)
        self._rate_val_lbl = QLabel(f"{saved_rate:+d}%  （负数=慢，正数=快）")
        self._rate_val_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")
        self._rate_slider.valueChanged.connect(self._on_rate_changed)
        rate_row.addWidget(self._rate_slider)
        rate_row.addWidget(self._rate_val_lbl)
        voice_form.addRow("朗读语速：", rate_row)

        voice_card.layout().addLayout(voice_form)

        test_voice_btn = QPushButton("🔊  试听效果")
        test_voice_btn.setObjectName("btn_secondary")
        test_voice_btn.setFixedHeight(34)
        test_voice_btn.clicked.connect(self._test_voice)
        voice_hint = QLabel("使用 Microsoft Edge 神经网络语音，无需额外API，免费高质量")
        voice_hint.setStyleSheet(f"font-size: 11px; color: {PALETTE['text_hint']};")

        btn_row_v = QHBoxLayout()
        btn_row_v.addWidget(test_voice_btn)
        btn_row_v.addWidget(voice_hint)
        btn_row_v.addStretch()
        voice_card.layout().addLayout(btn_row_v)
        layout.addWidget(voice_card)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._refresh_student_list()
        self._selected_student_id: int | None = None

    def _make_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setStyleSheet(
            f"QGroupBox {{ background: {PALETTE['card']}; border: 1px solid {PALETTE['border']};"
            f"border-radius: 12px; margin-top: 14px; padding: 16px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 16px; top: -4px;"
            f"font-size: 14px; font-weight: bold; color: {PALETTE['text_primary']}; }}"
        )
        box.setLayout(QVBoxLayout())
        box.layout().setSpacing(12)
        return box

    def _save_api(self):
        config.set_value("api_key", self._key_edit.text().strip())
        config.set_value("api_base_url", self._url_edit.text().strip() or "https://api.deepseek.com")
        config.set_value("model_chat", self._model_edit.text().strip() or "deepseek-chat")
        config.set_value("model_vision", self._vision_edit.text().strip())
        QMessageBox.information(self, "已保存", "API 设置已保存")

    def _test_api(self):
        key = self._key_edit.text().strip()
        url = self._url_edit.text().strip() or "https://api.deepseek.com"
        model = self._model_edit.text().strip() or "deepseek-chat"
        if not key:
            QMessageBox.warning(self, "提示", "请先填写 API Key")
            return
        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试中...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=url)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "回复'OK'"}],
                max_tokens=10,
            )
            msg = resp.choices[0].message.content.strip()
            QMessageBox.information(self, "连接成功", f"API 连接正常！\n模型回复：{msg}")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"错误：{e}")
        finally:
            self._test_btn.setEnabled(True)
            self._test_btn.setText("🔗  测试连接")

    def _refresh_student_list(self):
        self._student_list.clear()
        students = db.get_all_students()
        default_id = config.get("default_student_id")
        for s in students:
            is_default = str(s["id"]) == str(default_id)
            text = f"{'★ ' if is_default else ''}  {s['name']}  ·  {s['grade']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            self._student_list.addItem(item)
        if default_id:
            s = db.get_student(int(default_id))
            if s:
                self._current_student_lbl.setText(f"当前学生：{s['name']}  ({s['grade']})")

    def _on_student_select(self, item: QListWidgetItem):
        self._selected_student_id = item.data(Qt.ItemDataRole.UserRole)
        self._set_default_btn.setEnabled(True)
        self._edit_grade_btn.setEnabled(True)

    def _add_student(self):
        dlg = AddStudentDialog(self)
        if dlg.exec():
            name, grade = dlg.get_data()
            if not name:
                QMessageBox.warning(self, "提示", "请填写学生姓名")
                return
            sid = db.create_student(name, grade)
            # 如果是第一个学生，自动设为默认
            if len(db.get_all_students()) == 1:
                config.set_value("default_student_id", sid)
            self._refresh_student_list()
            if hasattr(self.parent(), "parent") and hasattr(self.parent().parent(), "refresh_student"):
                self.parent().parent().refresh_student()

    def _set_default_student(self):
        if self._selected_student_id:
            config.set_value("default_student_id", self._selected_student_id)
            self._refresh_student_list()
            # 通知主窗口刷新
            mw = self._find_main_window()
            if mw:
                mw.refresh_student()

    def _edit_student_grade(self):
        if not self._selected_student_id:
            return
        s = db.get_student(self._selected_student_id)
        if not s:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("修改年级")
        dlg.setFixedSize(280, 140)
        dl = QVBoxLayout(dlg)
        dl.setContentsMargins(20, 20, 20, 12)
        form = QFormLayout()
        combo = QComboBox()
        combo.addItems(GRADES)
        combo.setCurrentText(s["grade"])
        form.addRow("年级：", combo)
        dl.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        dl.addWidget(btns)
        if dlg.exec():
            db.update_student(self._selected_student_id, s["name"], combo.currentText())
            self._refresh_student_list()

    def _find_main_window(self):
        w = self
        while w:
            from ui.main_window import MainWindow
            if isinstance(w, MainWindow):
                return w
            w = w.parent()
        return None

    def _save_voice(self):
        name = self._voice_combo.currentText()
        voice = tts_engine.VOICES.get(name, tts_engine.DEFAULT_VOICE)
        config.set_value("tts_voice", voice)

    def _on_rate_changed(self, val: int):
        self._rate_val_lbl.setText(f"{val:+d}%  （负数=慢，正数=快）")
        config.set_value("tts_rate", f"{val:+d}%")

    def _test_voice(self):
        voice_name = self._voice_combo.currentText()
        voice = tts_engine.VOICES.get(voice_name, tts_engine.DEFAULT_VOICE)
        rate = f"{self._rate_slider.value():+d}%"
        tts_engine.speak(
            f"你好，我是{voice_name.split('（')[0]}，这是语音讲解功能的试听效果。"
            f"同学，加油学习数学，你一定可以的！",
            voice=voice,
            rate=rate,
        )

    def _save_teaching(self):
        config.set_value("region", self._region_combo.currentText())
        config.set_value("textbook_version", self._textbook_combo.currentText())
        self._refresh_teach_hint()

    def _refresh_teach_hint(self):
        from data.regions import REGION_INFO, TEXTBOOKS as TB
        region = self._region_combo.currentText()
        tb = self._textbook_combo.currentText()
        lines = []
        if region != "全国通用":
            info = REGION_INFO.get(region)
            if info:
                lines.append(f"出题风格：{info['exam_style']}")
        tb_desc = TB.get(tb, "")
        if tb_desc:
            lines.append(f"教材说明：{tb_desc}")
        if lines:
            self._teach_hint.setText("\n".join(lines))
            self._teach_hint.show()
        else:
            self._teach_hint.hide()

    def on_activate(self):
        self._refresh_student_list()
