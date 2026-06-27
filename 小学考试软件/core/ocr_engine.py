"""
OCR引擎：优先用视觉模型，fallback用easyocr + DeepSeek解析
"""
import os
import cv2
import numpy as np
from PIL import Image
import config
from core import ai_engine


def preprocess_image(image_path: str) -> np.ndarray:
    """图像预处理：灰度化、对比度增强、去噪"""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 自适应直方图均衡化，增强对比度
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    # 去噪
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
    return denoised


_easyocr_reader = None


def ocr_with_easyocr(image_path: str) -> str:
    """使用easyocr提取文本（Reader 全局缓存，避免重复初始化）"""
    global _easyocr_reader
    try:
        import easyocr
        if _easyocr_reader is None:
            _easyocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
        results = _easyocr_reader.readtext(image_path, detail=0, paragraph=False)
        return "\n".join(results)
    except ImportError:
        raise RuntimeError("easyocr未安装，请运行: pip install easyocr")


def extract_answers(image_path: str, question_count: int) -> dict:
    """
    主入口：从图片提取学生答案
    返回: {"1": "A", "2": "25", ...}
    优先尝试视觉模型，失败则降级到OCR+文字解析
    """
    # 先尝试视觉模型
    try:
        result = ai_engine.parse_handwritten_answers_vision(image_path, question_count)
        if result and "answers" in result:
            return result["answers"]
    except Exception:
        pass

    # 降级：OCR提取文本 → DeepSeek解析结构
    try:
        text = ocr_with_easyocr(image_path)
    except Exception as e:
        raise RuntimeError(f"OCR识别失败: {e}")

    if not text.strip():
        raise RuntimeError("图片中未识别到文字，请检查图片清晰度")

    result = ai_engine.parse_handwritten_answers(text, question_count)
    return result.get("answers", {})


def check_image_quality(image_path: str) -> tuple[bool, str]:
    """
    检查图片质量，返回 (是否合格, 提示信息)
    """
    img = cv2.imread(image_path)
    if img is None:
        return False, "无法读取图片文件"

    h, w = img.shape[:2]
    if h < 400 or w < 400:
        return False, f"图片分辨率过低（{w}×{h}），建议重新拍摄"

    # 模糊检测（拉普拉斯方差）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if lap_var < 100:
        return False, f"图片较模糊（清晰度分数{lap_var:.0f}），建议重新拍摄"

    # 亮度检测
    mean_brightness = gray.mean()
    if mean_brightness < 50:
        return False, "图片过暗，请在光线充足的环境下拍摄"
    if mean_brightness > 230:
        return False, "图片过亮，请避免强光直射"

    return True, f"图片质量良好（清晰度{lap_var:.0f}，亮度{mean_brightness:.0f}）"
