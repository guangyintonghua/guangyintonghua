from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from data import database as db
import config

router = APIRouter(tags=["students"])


class StudentIn(BaseModel):
    name: str
    grade: str


@router.get("/students")
def list_students():
    return db.get_all_students()


@router.post("/students")
def create_student(body: StudentIn):
    sid = db.create_student(body.name, body.grade)
    return {"id": sid}


@router.put("/students/{sid}")
def update_student(sid: int, body: StudentIn):
    db.update_student(sid, body.name, body.grade)
    return {"ok": True}


@router.delete("/students/{sid}")
def delete_student(sid: int):
    with db.get_conn() as conn:
        conn.execute("DELETE FROM students WHERE id=?", (sid,))
    return {"ok": True}


@router.get("/students/current")
def current_student():
    sid = config.get("default_student_id")
    if not sid:
        return None
    s = db.get_student(int(sid))
    if not s:
        return None
    s["points"] = db.get_total_points(s["id"])
    s["streak"] = db.get_streak(s["id"])
    s["badges"] = db.get_badges(s["id"])
    return s


@router.get("/stats")
def home_stats():
    sid = config.get("default_student_id")
    if not sid:
        return {}
    stats = db.get_weekly_stats(int(sid))
    subs = db.get_student_submissions(int(sid), limit=8)
    kp = db.get_kp_mastery(int(sid))
    weak = [k for k in kp if k["rate"] < 0.6][:3]
    return {**stats, "recent_submissions": subs, "weak_kps": weak}
