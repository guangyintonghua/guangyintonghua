import os
import json
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from api.tasks import create_task, run_task
from data import database as db
from core import ai_engine, ocr_engine, analyzer
import config

router = APIRouter(tags=["submissions"])


@router.post("/submissions/ocr")
async def ocr_image(file: UploadFile = File(...), question_count: int = Form(...)):
    suffix = os.path.splitext(file.filename or "img.jpg")[1] or ".jpg"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(await file.read())
    tmp.close()

    ok, quality_msg = ocr_engine.check_image_quality(tmp.name)

    tid = create_task()
    run_task(tid, ocr_engine.extract_answers, tmp.name, question_count)
    return {"task_id": tid, "quality_ok": ok, "quality_msg": quality_msg, "tmp_path": tmp.name}


class SubmitBody(BaseModel):
    exam_id: int
    answers: dict[str, str]
    image_path: str = ""


@router.post("/submissions")
def submit_answers(body: SubmitBody):
    sid = config.get("default_student_id")
    if not sid:
        raise HTTPException(400, "请先选择学生")

    exam = db.get_exam(body.exam_id)
    if not exam:
        raise HTTPException(404, "试卷不存在")

    tid = create_task()

    def _grade():
        graded = ai_engine.grade_all(exam["questions"], body.answers)
        kp_stats = analyzer.compute_kp_stats(graded)
        score, total = analyzer.compute_score(graded)
        student_id = int(sid)

        sub_id = db.save_submission(
            exam_id=body.exam_id,
            student_id=student_id,
            answers=body.answers,
            graded_results=graded,
            analysis={},
            kp_stats=kp_stats,
            score=score,
            total_score=total,
            image_path=body.image_path,
        )
        db.update_kp_mastery(student_id, exam.get("grade", ""), kp_stats)

        correct = sum(1 for r in graded if r["grading"]["is_correct"])
        db.award_points(student_id, 10 + correct * 2, "完成批改")
        if score >= total > 0:
            db.award_points(student_id, 20, "满分奖励")
        db.checkin_today(student_id, len(graded))
        db.check_and_award_badges(student_id)

        student = db.get_student(student_id)
        try:
            analysis = ai_engine.analyze_results(
                student["name"] if student else "学生",
                exam.get("grade", ""), exam.get("semester", ""),
                graded, kp_stats,
            )
        except Exception:
            analysis = {}

        if analysis:
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE submissions SET analysis=? WHERE id=?",
                    (json.dumps(analysis, ensure_ascii=False), sub_id),
                )

        return {"sub_id": sub_id, "score": score, "total": total}

    run_task(tid, _grade)
    return {"task_id": tid}


@router.get("/submissions")
def list_submissions():
    sid = config.get("default_student_id")
    if not sid:
        return []
    return db.get_student_submissions(int(sid))


@router.get("/submissions/{sub_id}")
def get_submission(sub_id: int):
    sub = db.get_submission(sub_id)
    if not sub:
        raise HTTPException(404, "记录不存在")
    return sub
