import asyncio
import os
import tempfile
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from core import ai_engine

router = APIRouter(tags=["tts"])

VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "-10%"


async def _synthesize(text: str, path: str):
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate=RATE)
    await comm.save(path)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


class QuestionBody(BaseModel):
    question: dict
    grade: str = ""


class KpBody(BaseModel):
    knowledge_point: str
    grade: str = ""


@router.post("/tts/question")
async def tts_question(body: QuestionBody):
    text = ai_engine.generate_voice_explanation(body.question, body.grade)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    await _synthesize(text, tmp.name)
    return FileResponse(tmp.name, media_type="audio/mpeg",
                        background=_cleanup(tmp.name))


@router.post("/tts/knowledge-point")
async def tts_kp(body: KpBody):
    text = ai_engine.generate_voice_kp_explanation(body.knowledge_point, body.grade)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    await _synthesize(text, tmp.name)
    return FileResponse(tmp.name, media_type="audio/mpeg",
                        background=_cleanup(tmp.name))


class _cleanup:
    def __init__(self, path: str):
        self.path = path

    async def __call__(self):
        try:
            os.unlink(self.path)
        except Exception:
            pass
