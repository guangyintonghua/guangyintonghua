from fastapi import APIRouter
from data import database as db
import config

router = APIRouter(tags=["wrong_book"])


@router.get("/wrong-book")
def get_wrong_book(kp: str = None):
    sid = config.get("default_student_id")
    if not sid:
        return []
    return db.get_all_wrong_answers(int(sid), kp_filter=kp or None)


@router.get("/wrong-book/kps")
def get_wrong_kps():
    sid = config.get("default_student_id")
    if not sid:
        return []
    return db.get_wrong_kp_list(int(sid))
