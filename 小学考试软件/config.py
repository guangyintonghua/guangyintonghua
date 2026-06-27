import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "data", "config.json")

DEFAULTS = {
    "api_key": "",
    "api_base_url": "https://api.deepseek.com",
    "model_chat": "deepseek-chat",
    "model_vision": "deepseek-vl",
    "default_grade": "三年级",
    "default_student": "学生",
    "theme": "light",
    "region": "全国通用",
    "textbook_version": "人教版（PEP）",
}


def load() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return DEFAULTS.copy()


def save(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get(key: str):
    return load().get(key, DEFAULTS.get(key))


def set_value(key: str, value):
    cfg = load()
    cfg[key] = value
    save(cfg)
