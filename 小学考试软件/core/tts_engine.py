"""
语音引擎：Microsoft Edge TTS（免费、高质量中文语音）
DeepSeek 生成讲解文本 → Edge TTS 合成语音 → pygame 播放
"""
import asyncio
import os
import tempfile
import threading
from pathlib import Path

import edge_tts
import pygame

# 可用的中文语音
VOICES = {
    "晓晓（女·温柔）": "zh-CN-XiaoxiaoNeural",
    "云希（男·亲切）": "zh-CN-YunxiNeural",
    "晓伊（女·活泼）": "zh-CN-XiaoyiNeural",
    "云扬（男·专业）": "zh-CN-YunyangNeural",
}
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

_pygame_init = False
_current_thread: threading.Thread | None = None
_stop_flag = threading.Event()


def _ensure_pygame():
    global _pygame_init
    if not _pygame_init:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        _pygame_init = True


def _run_async(coro):
    """在新事件循环中运行异步函数"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _synthesize(text: str, voice: str, output_path: str, rate: str = "+0%"):
    comm = edge_tts.Communicate(text, voice, rate=rate)
    await comm.save(output_path)


def speak(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "-10%",
    on_start=None,
    on_finish=None,
    on_error=None,
):
    """
    异步朗读文本（不阻塞UI线程）
    rate: "-10%" 稍慢，适合讲解；"+0%"正常速度
    """
    global _current_thread, _stop_flag

    # 停止上一段播放
    stop()
    _stop_flag.clear()

    def _worker():
        try:
            # 合成音频到临时文件
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_path = tmp.name
            tmp.close()

            _run_async(_synthesize(text, voice, tmp_path, rate))

            if _stop_flag.is_set():
                return

            if on_start:
                on_start()

            # 播放
            _ensure_pygame()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            # 等待播放完成或停止信号
            while pygame.mixer.music.get_busy():
                if _stop_flag.is_set():
                    pygame.mixer.music.stop()
                    break
                pygame.time.Clock().tick(10)

            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            if not _stop_flag.is_set() and on_finish:
                on_finish()

        except Exception as e:
            if on_error:
                on_error(str(e))

    _current_thread = threading.Thread(target=_worker, daemon=True)
    _current_thread.start()


def stop():
    """停止当前播放"""
    global _stop_flag
    _stop_flag.set()
    try:
        if _pygame_init and pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def is_playing() -> bool:
    try:
        return _pygame_init and pygame.mixer.get_init() and pygame.mixer.music.get_busy()
    except Exception:
        return False


def get_voices() -> dict:
    return VOICES
