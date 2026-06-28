from fastapi import APIRouter
from pydantic import BaseModel
from core.knowledge_map import KNOWLEDGE_TREE
import config

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    api_key: str = None
    api_base_url: str = None
    model_chat: str = None
    default_grade: str = None
    default_student_id: str = None
    region: str = None
    textbook_version: str = None


@router.get("/settings")
def get_settings():
    cfg = config.load()
    cfg.pop("api_key", None)   # 不返回明文 key 到前端（仅设置页显示）
    return cfg


@router.get("/settings/full")
def get_settings_full():
    return config.load()


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    for k, v in body.dict(exclude_none=True).items():
        config.set_value(k, v)
    return {"ok": True}


@router.get("/knowledge-map")
def knowledge_map(grade: str = None, semester: str = None):
    if grade and grade in KNOWLEDGE_TREE:
        tree = KNOWLEDGE_TREE[grade]
        if semester and semester in tree:
            return tree[semester]
        return tree
    grades = list(KNOWLEDGE_TREE.keys())
    return {"grades": grades, "tree": KNOWLEDGE_TREE}
