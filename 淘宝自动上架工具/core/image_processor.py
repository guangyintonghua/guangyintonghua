# -*- coding: utf-8 -*-
"""
图片路径读取，支持两种目录结构：

新格式（产品文件夹模式）：
  产品文件夹/
    主图/          ← 所有图片均为主图，按文件名排序取前5张
    详情图/        ← 所有图片均为详情图

旧格式（序号文件夹模式）：
  序号文件夹/
    主图_1.jpg, 主图_2.jpg ...   → main_images（最多5张）
    详情_1.jpg, 详情_2.jpg ...   → detail_images
    sku_红色.jpg                 → sku_images
"""
from pathlib import Path
from loguru import logger
from models.product import Product

_IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


def _sort_key(p: Path) -> tuple:
    # 提取文件名中的数字用于排序
    digits = ''.join(c for c in p.stem if c.isdigit())
    return (int(digits) if digits else 9999, p.name)


def _images_in(folder: Path) -> list[Path]:
    """返回文件夹内所有图片，按名称排序"""
    return sorted(
        [f for f in folder.iterdir()
         if f.is_file() and f.suffix.lower() in _IMG_EXT],
        key=_sort_key
    )


def _find_dir(src: Path, keywords: tuple) -> Path | None:
    """在 src 下找第一个匹配 keyword 的目录。
    先精确匹配，再找名称以 keyword 结尾的子目录（如 '1号品1比1主图'）。"""
    for kw in keywords:
        d = src / kw
        if d.is_dir():
            return d
    for kw in keywords:
        for d in src.iterdir():
            if d.is_dir() and d.name.endswith(kw):
                return d
    return None


def load_product_images(product: Product) -> None:
    if product.image_dir is None or not product.image_dir.is_dir():
        logger.warning(f"[{product.seq}] 图片目录不存在: {product.image_dir}")
        return

    src = product.image_dir

    # ── 1:1主图 ────────────────────────────────────────────────────────
    d = _find_dir(src, ('主图', '1比1主图', 'main', '主图片'))
    product.main_images = _images_in(d)[:5] if d else []
    if not product.main_images:
        product.main_images = sorted(
            [f for f in src.iterdir()
             if f.is_file() and f.stem.startswith('主图_')
             and f.suffix.lower() in _IMG_EXT],
            key=_sort_key
        )[:5]

    # ── 3:4主图（竖版主图）─────────────────────────────────────────────
    d = _find_dir(src, ('3比4主图', '竖版主图', '竖图', '3x4主图'))
    product.main_images_3x4 = _images_in(d)[:5] if d else []

    # ── 白底图（最多1张）──────────────────────────────────────────────
    d = _find_dir(src, ('白底图', '白底'))
    product.white_bg_images = _images_in(d)[:1] if d else []

    # ── 卖点图 ─────────────────────────────────────────────────────────
    d = _find_dir(src, ('卖点图', '卖点', '亮点图', '亮点'))
    product.selling_images = _images_in(d) if d else []

    # ── 详情图 ─────────────────────────────────────────────────────────
    d = _find_dir(src, ('详情图', '详情页', 'detail', '详情'))
    product.detail_images = _images_in(d) if d else []
    if not product.detail_images:
        product.detail_images = sorted(
            [f for f in src.iterdir()
             if f.is_file() and f.stem.startswith('详情_')
             and f.suffix.lower() in _IMG_EXT],
            key=_sort_key
        )

    # SKU 颜色图（两种格式均从 src 根目录找）
    for f in src.iterdir():
        if f.is_file() and f.stem.startswith('sku_') \
                and f.suffix.lower() in _IMG_EXT:
            color = f.stem[4:]
            product.sku_images[color] = f

    logger.info(f"[{product.seq}] 图片: 1:1主图 {len(product.main_images)} 张  "
                f"3:4主图 {len(product.main_images_3x4)} 张  "
                f"白底图 {len(product.white_bg_images)} 张  "
                f"卖点图 {len(product.selling_images)} 张  "
                f"详情 {len(product.detail_images)} 张  "
                f"SKU颜色图 {len(product.sku_images)} 张")
