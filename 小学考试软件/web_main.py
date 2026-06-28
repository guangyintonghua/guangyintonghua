import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from utils import logger as _logger
log = _logger.setup()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import config
from data.database import init_db
from utils.cache import clear_expired

app = FastAPI(title="小学数学智能练习系统")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

from api import students, exams, submissions, practice, wrong_book, speed_calc, settings as settings_api, tts

for router in [students.router, exams.router, submissions.router,
               practice.router, wrong_book.router, speed_calc.router,
               settings_api.router, tts.router]:
    app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup():
    init_db()
    try:
        clear_expired()
    except Exception:
        pass
    if not config.get("api_key"):
        config.set_value("api_key", "sk-40c9751c22c14ef4ae78acb990cdf1ca")
    log.info("Web server started")


def _page(tpl: str):
    async def handler(request: Request):
        return templates.TemplateResponse(request=request, name=tpl)
    handler.__name__ = f"page_{tpl}"
    return handler


app.get("/",            response_class=HTMLResponse)(_page("home.html"))
app.get("/exam",        response_class=HTMLResponse)(_page("exam.html"))
app.get("/submit",      response_class=HTMLResponse)(_page("submit.html"))
app.get("/report",      response_class=HTMLResponse)(_page("report.html"))
app.get("/practice",    response_class=HTMLResponse)(_page("practice.html"))
app.get("/wrong-book",  response_class=HTMLResponse)(_page("wrong_book.html"))
app.get("/speed-calc",  response_class=HTMLResponse)(_page("speed_calc.html"))
app.get("/settings",    response_class=HTMLResponse)(_page("settings.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_main:app", host="0.0.0.0", port=8000, reload=False)
