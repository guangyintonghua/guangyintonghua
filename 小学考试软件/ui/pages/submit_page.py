from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QLineEdit, QGridLayout,
    QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QPixmap, QFont

import os
import config
from data import database as db
from core import ai_engine, ocr_engine, analyzer
from ui.styles import PALETTE


class OCRWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, image_path: str, question_count: int):
        super().__init__()
        self.image_path = image_path
        self.question_count = question_count

    def run(self):
        try:
            answers = ocr_engine.extract_answers(self.image_path, self.question_count)
            self.finished.emit(answers)
        except Exception as e:
            self.error.emit(str(e))


class GradeWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, questions: list, answers: dict):
        super().__init__()
        self.questions = questions
        self.answers = answers

    def run(self):
        try:
            results = ai_engine.grade_all(self.questions, self.answers)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AnalyzeWorker(QThread):
    """在后台线程中执行 AI 深度分析，避免阻塞主线程。"""
    finished = pyqtSignal(dict)

    def __init__(self, student_name, grade, semester, graded_results, kp_stats):
        super().__init__()
        self.student_name = student_name
        self.grade = grade
        self.semester = semester
        self.graded_results = graded_results
        self.kp_stats = kp_stats

    def run(self):
        try:
            result = ai_engine.analyze_results(
                self.student_name, self.grade, self.semester,
                self.graded_results, self.kp_stats,
            )
        except Exception:
            result = {}
        self.finished.emit(result)


class SubmitPage(QWidget):
    submission_done = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._exam: dict | None = None
        self._image_path: str = ""
        self._recognized_answers: dict = {}
        self._answer_edits: dict[str, QLineEdit] = {}
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(20)

        # 页头
        header = QHBoxLayout()
        title = QLabel("上传作答")
        title.setObjectName("label_title")
        header.addWidget(title)
        header.addStretch()
        self._exam_label = QLabel("未选择试卷")
        self._exam_label.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 13px;")
        header.addWidget(self._exam_label)
        main_layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        # ── 左：图片上传 ──────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(12)

        # 图片预览区
        self._img_frame = QFrame()
        self._img_frame.setObjectName("card")
        self._img_frame.setMinimumHeight(350)
        img_inner = QVBoxLayout(self._img_frame)
        img_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._img_label = QLabel("点击上传照片\n或将图片拖拽到此处")
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet(f"color: {PALETTE['text_hint']}; font-size: 14px;")
        img_inner.addWidget(self._img_label)
        left_layout.addWidget(self._img_frame, 1)

        # 质量提示
        self._quality_label = QLabel("")
        self._quality_label.setStyleSheet(f"font-size: 12px;")
        left_layout.addWidget(self._quality_label)

        # 上传按钮
        upload_row = QHBoxLayout()
        self._upload_btn = QPushButton("📁  选择图片文件")
        self._upload_btn.setObjectName("btn_secondary")
        self._upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_btn.clicked.connect(self._on_upload)
        upload_row.addWidget(self._upload_btn)

        self._ocr_btn = QPushButton("🔍  识别手写答案")
        self._ocr_btn.setObjectName("btn_primary")
        self._ocr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ocr_btn.setEnabled(False)
        self._ocr_btn.clicked.connect(self._on_ocr)
        upload_row.addWidget(self._ocr_btn)
        left_layout.addLayout(upload_row)

        self._ocr_progress = QProgressBar()
        self._ocr_progress.setRange(0, 0)
        self._ocr_progress.setFixedHeight(4)
        self._ocr_progress.hide()
        left_layout.addWidget(self._ocr_progress)

        splitter.addWidget(left)

        # ── 右：答案确认 & 提交 ───────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(12)

        confirm_lbl = QLabel("确认答案")
        confirm_lbl.setObjectName("label_section")
        right_layout.addWidget(confirm_lbl)

        hint = QLabel("上传答卷照片后点击「识别手写答案」，再点击批改")
        hint.setStyleSheet(f"color: {PALETTE['text_hint']}; font-size: 12px;")
        right_layout.addWidget(hint)

        # 答案列表（可编辑）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._answer_container = QWidget()
        self._answer_grid = QGridLayout(self._answer_container)
        self._answer_grid.setSpacing(8)
        self._answer_grid.setColumnStretch(1, 1)
        scroll.setWidget(self._answer_container)
        right_layout.addWidget(scroll, 1)

        # 进度条（批改用）
        self._grade_progress = QProgressBar()
        self._grade_progress.setRange(0, 0)
        self._grade_progress.setFixedHeight(4)
        self._grade_progress.hide()
        right_layout.addWidget(self._grade_progress)

        # 底部按钮
        btn_row = QHBoxLayout()
        self._submit_btn = QPushButton("✅  开始批改  →")
        self._submit_btn.setObjectName("btn_primary")
        self._submit_btn.setFixedHeight(44)
        self._submit_btn.setEnabled(False)
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._submit_btn)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([500, 580])

    def load_exam(self, exam_id: int):
        self._exam = db.get_exam(exam_id)
        if self._exam:
            title = self._exam.get("title", "未命名")
            count = len(self._exam.get("questions", []))
            self._exam_label.setText(f"📋 {title}  ·  共{count}题")
            # 清空上一次状态
            self._image_path = ""
            self._recognized_answers = {}
            self._clear_answer_grid()
            self._img_label.setText("点击上传照片\n或将图片拖拽到此处")
            self._img_label.setPixmap(QPixmap())
            self._quality_label.setText("")
            self._ocr_btn.setEnabled(False)
            self._submit_btn.setEnabled(False)

    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择答题照片", "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        if not path:
            return
        self._image_path = path
        self._show_image(path)

        ok, msg = ocr_engine.check_image_quality(path)
        color = PALETTE["success"] if ok else PALETTE["warning"]
        icon = "✓" if ok else "⚠"
        self._quality_label.setText(f"{icon} {msg}")
        self._quality_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._ocr_btn.setEnabled(True)

    def _show_image(self, path: str):
        px = QPixmap(path)
        if not px.isNull():
            scaled = px.scaled(
                self._img_frame.width() - 20, self._img_frame.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._img_label.setPixmap(scaled)
            self._img_label.setText("")

    def _on_ocr(self):
        if not self._image_path or not self._exam:
            return
        q_count = len(self._exam.get("questions", []))
        self._ocr_btn.setEnabled(False)
        self._ocr_btn.setText("识别中...")
        self._ocr_progress.show()

        self._ocr_worker = OCRWorker(self._image_path, q_count)
        self._ocr_worker.finished.connect(self._on_ocr_done)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()

    @pyqtSlot(dict)
    def _on_ocr_done(self, answers: dict):
        self._ocr_progress.hide()
        self._ocr_btn.setEnabled(True)
        self._ocr_btn.setText("🔍  识别手写答案")
        self._recognized_answers = answers
        self._build_answer_grid(answers)
        self._submit_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_ocr_error(self, err: str):
        self._ocr_progress.hide()
        self._ocr_btn.setEnabled(True)
        self._ocr_btn.setText("🔍  识别手写答案")
        QMessageBox.warning(self, "识别失败", f"OCR识别出错：\n{err}\n\n请检查图片质量后重新上传")

    def _build_answer_grid(self, answers: dict):
        self._clear_answer_grid()
        if not self._exam:
            return
        questions = self._exam.get("questions", [])

        # 表头
        for col, text in enumerate(["题号", "题目（摘要）", "识别答案"]):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-weight: bold; color: {PALETTE['text_secondary']}; font-size: 12px;")
            self._answer_grid.addWidget(lbl, 0, col)

        self._answer_edits = {}
        for i, q in enumerate(questions, 1):
            qid = str(q["id"])
            # 题号
            num_lbl = QLabel(f"第{q['id']}题")
            num_lbl.setStyleSheet("font-size: 13px; min-width: 50px;")
            self._answer_grid.addWidget(num_lbl, i, 0)

            # 题目摘要
            content = q["content"][:20] + "..." if len(q["content"]) > 20 else q["content"]
            q_lbl = QLabel(content)
            q_lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE['text_secondary']};")
            q_lbl.setWordWrap(True)
            self._answer_grid.addWidget(q_lbl, i, 1)

            # 答案编辑框
            edit = QLineEdit(answers.get(qid, ""))
            edit.setPlaceholderText("未识别，手动填写")
            edit.setFixedHeight(32)
            self._answer_grid.addWidget(edit, i, 2)
            self._answer_edits[qid] = edit

        self._submit_btn.setEnabled(True)

    def _clear_answer_grid(self):
        while self._answer_grid.count():
            item = self._answer_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._answer_edits.clear()

    def _on_submit(self):
        if not self._exam:
            QMessageBox.warning(self, "提示", "请先选择试卷")
            return
        sid = config.get("default_student_id")
        if not sid:
            QMessageBox.warning(self, "提示", "请先在设置中选择学生")
            return

        answers = {qid: edit.text().strip() for qid, edit in self._answer_edits.items()}
        if not any(answers.values()):
            QMessageBox.warning(self, "提示", "请先填写或识别答案")
            return

        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("批改中...")
        self._grade_progress.show()

        self._grade_worker = GradeWorker(self._exam.get("questions", []), answers)
        self._grade_worker.finished.connect(lambda r: self._on_graded(r, answers, int(sid)))
        self._grade_worker.error.connect(self._on_grade_error)
        self._grade_worker.start()

    @pyqtSlot(list)
    def _on_graded(self, graded_results: list, answers: dict, student_id: int):
        self._grade_progress.hide()
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("✅  开始批改  →")

        kp_stats = analyzer.compute_kp_stats(graded_results)
        score, total = analyzer.compute_score(graded_results)
        exam = self._exam
        student = db.get_student(student_id)

        # 先用空 analysis 保存，拿到 sub_id，后台异步补充分析
        sub_id = db.save_submission(
            exam_id=exam["id"],
            student_id=student_id,
            answers=answers,
            graded_results=graded_results,
            analysis={},
            kp_stats=kp_stats,
            score=score,
            total_score=total,
            image_path=self._image_path,
        )
        db.update_kp_mastery(student_id, exam.get("grade", ""), kp_stats)

        # 积分 & 打卡
        q_count = len(graded_results)
        correct = sum(1 for r in graded_results if r.get("grading", {}).get("is_correct"))
        db.award_points(student_id, 10 + correct * 2, "完成批改")
        if score >= total > 0:
            db.award_points(student_id, 20, "满分奖励")
        db.checkin_today(student_id, q_count)

        self.submission_done.emit(sub_id)

        # 后台生成 AI 深度分析，完成后更新数据库
        self._analyze_worker = AnalyzeWorker(
            student_name=student["name"] if student else "学生",
            grade=exam.get("grade", ""),
            semester=exam.get("semester", ""),
            graded_results=graded_results,
            kp_stats=kp_stats,
        )
        self._analyze_worker.finished.connect(
            lambda a: self._on_analysis_done(sub_id, a)
        )
        self._analyze_worker.start()

    def _on_analysis_done(self, sub_id: int, analysis: dict):
        """后台分析完成后更新 submission 记录。"""
        if not analysis:
            return
        try:
            import json as _json
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE submissions SET analysis=? WHERE id=?",
                    (_json.dumps(analysis, ensure_ascii=False), sub_id),
                )
        except Exception:
            pass

    @pyqtSlot(str)
    def _on_grade_error(self, err: str):
        self._grade_progress.hide()
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("✅  开始批改  →")
        QMessageBox.critical(self, "批改失败", f"AI批改出错：\n{err}")
