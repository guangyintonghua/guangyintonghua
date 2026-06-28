from fastapi import APIRouter
from pydantic import BaseModel
from api.tasks import create_task, run_task
from core import ai_engine
import config

router = APIRouter(tags=["practice"])


class PracticeRequest(BaseModel):
    knowledge_point: str
    count: int = 6


class GradeRequest(BaseModel):
    question: dict
    student_answer: str


class GuideRequest(BaseModel):
    question: dict
    history: list[dict]


@router.post("/practice/generate")
def generate_practice(body: PracticeRequest):
    grade = config.get("default_grade") or "三年级"
    tid = create_task()
    run_task(tid, ai_engine.generate_practice, body.knowledge_point, grade, body.count)
    return {"task_id": tid}


@router.post("/practice/grade")
def grade_answer(body: GradeRequest):
    return ai_engine.grade_question(body.question, body.student_answer)


@router.post("/practice/guide")
def guide(body: GuideRequest):
    grade = config.get("default_grade") or "三年级"
    reply = ai_engine.guide_student(body.question, grade, body.history)
    return {"reply": reply}


@router.post("/practice/steps")
def get_steps(body: GradeRequest):
    grade = config.get("default_grade") or "三年级"
    return ai_engine.get_solution_steps(body.question, grade)
