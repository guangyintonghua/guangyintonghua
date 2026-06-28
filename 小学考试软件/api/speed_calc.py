import random
from fastapi import APIRouter
from pydantic import BaseModel
from data import database as db
import config

router = APIRouter(tags=["speed_calc"])


class CalcConfig(BaseModel):
    ops: list[str] = ["+", "-"]
    max_num: int = 20
    count: int = 20


class CalcResult(BaseModel):
    questions: list[dict]
    time_seconds: float


@router.post("/speed-calc/generate")
def generate(body: CalcConfig):
    questions = []
    for i in range(body.count):
        op = random.choice(body.ops)
        if op == "+":
            a = random.randint(1, body.max_num)
            b = random.randint(1, body.max_num)
            q, ans = f"{a} + {b}", a + b
        elif op == "-":
            a = random.randint(1, body.max_num)
            b = random.randint(0, a)
            q, ans = f"{a} - {b}", a - b
        elif op == "×":
            a = random.randint(1, min(body.max_num, 9))
            b = random.randint(1, min(body.max_num, 9))
            q, ans = f"{a} × {b}", a * b
        elif op == "÷":
            b = random.randint(1, min(body.max_num, 9))
            c = random.randint(1, min(body.max_num // max(b, 1), 9))
            a = b * c
            q, ans = f"{a} ÷ {b}", c
        else:
            continue
        questions.append({"id": i + 1, "q": q, "answer": ans})
    return questions


@router.post("/speed-calc/submit")
def submit(body: CalcResult):
    correct = sum(
        1 for q in body.questions
        if str(q.get("student_answer", "")).strip() == str(q["answer"])
    )
    total = len(body.questions)
    sid = config.get("default_student_id")

    if sid:
        student_id = int(sid)
        db.award_points(student_id, correct * 1, "口算得分")
        if correct == total and total >= 10:
            db.award_points(student_id, 5, "口算全对")
        db.checkin_today(student_id, total)
        db.check_and_award_badges(student_id)

    return {
        "correct": correct,
        "total": total,
        "accuracy": round(correct / total * 100, 1) if total else 0,
        "time_seconds": body.time_seconds,
    }
