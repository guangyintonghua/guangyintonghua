from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from api.tasks import create_task, run_task, get_task
from data import database as db
from core import ai_engine
import config

router = APIRouter(tags=["exams"])


class ExamGenRequest(BaseModel):
    grade: str
    semester: str
    topics: list[str]
    type_counts: dict[str, list[int]]   # {"选择题": [count, score_each]}
    difficulty: list[int] = [40, 40, 20]


@router.post("/exams/generate")
def generate_exam(body: ExamGenRequest):
    sid = config.get("default_student_id")
    if not sid:
        raise HTTPException(400, "请先在设置中选择学生")

    type_counts = {k: tuple(v) for k, v in body.type_counts.items() if v[0] > 0}
    if not type_counts:
        raise HTTPException(400, "至少选择一种题型")

    tid = create_task()

    def _gen():
        result = ai_engine.generate_exam(
            body.grade, body.semester, body.topics,
            type_counts, tuple(body.difficulty),
        )
        questions = result.get("questions", [])
        total = result.get("total_score", 100)
        exam_id = db.save_exam(
            student_id=int(sid),
            title=f"{body.grade}{body.semester}数学练习",
            grade=body.grade,
            semester=body.semester,
            topics=body.topics,
            questions=questions,
            total_score=total,
        )
        return {"exam_id": exam_id, "questions": questions, "total_score": total}

    run_task(tid, _gen)
    return {"task_id": tid}


@router.get("/tasks/{tid}")
def poll_task(tid: str):
    return get_task(tid)


@router.get("/exams")
def list_exams():
    sid = config.get("default_student_id")
    if not sid:
        return []
    return db.get_recent_exams(int(sid))


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int):
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(404, "试卷不存在")
    return exam


@router.get("/exams/{exam_id}/pdf")
def download_pdf(exam_id: int):
    import tempfile, os
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(404, "试卷不存在")
    from utils.pdf_gen import generate_exam_pdf
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    generate_exam_pdf(exam, tmp.name)
    return FileResponse(
        tmp.name, media_type="application/pdf",
        filename=f"{exam.get('title','试卷')}.pdf",
    )


@router.get("/adaptive-difficulty")
def adaptive_difficulty(topics: str = ""):
    sid = config.get("default_student_id")
    if not sid:
        return {"easy": 40, "medium": 40, "hard": 20}
    topic_list = [t for t in topics.split(",") if t] if topics else None
    return db.get_adaptive_difficulty(int(sid), topic_list)
