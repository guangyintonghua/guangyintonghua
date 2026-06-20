# -*- coding: utf-8 -*-
"""
淘宝自动上架 — 生产脚本（真实提交，会点击发布按钮）

用法:
  python run_upload.py                          # 扫描默认产品文件夹
  python run_upload.py "路径\\到\\产品文件夹"   # 指定产品文件夹

前提:
  Chrome 已用调试模式启动（启动调试浏览器.bat），端口 9222
"""
import asyncio
import sys
import datetime
from pathlib import Path
from loguru import logger

# ── 默认配置 ──────────────────────────────────────────────────────────────────
DEFAULT_FOLDER  = Path(r'E:\AI工具\淘宝店运营流\桌布自动生图工作流\产品素材\1号品')
SHIPPING_TPL    = '光阴童话'
LOG_DIR         = Path(r'E:\AI工具\淘宝自动上架工具\logs')

# ─────────────────────────────────────────────────────────────────────────────

def _setup_logger():
    log_name = datetime.datetime.now().strftime('upload_%Y%m%d_%H%M%S.log')
    log_path = LOG_DIR / log_name
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    fmt = '<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}'
    logger.add(sys.stdout, level='DEBUG', format=fmt, colorize=False)
    logger.add(log_path,   level='DEBUG', format=fmt, encoding='utf-8')
    logger.info(f'日志路径: {log_path}')
    return log_path


async def main():
    log_path = _setup_logger()
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FOLDER

    # ── 1. 读取商品数据 ───────────────────────────────────────────────────────
    logger.info(f'=== 扫描商品文件夹: {folder} ===')
    from core.data_reader import scan_and_read_folder
    products = scan_and_read_folder(folder)
    logger.info(f'  共 {len(products)} 个商品待上架')
    for p in products:
        logger.info(f'  [{p.seq}] {p.title[:30]}  SKU数: {len(p.skus)}')

    # ── 2. 加载图片 ───────────────────────────────────────────────────────────
    logger.info('=== 加载图片 ===')
    from core.image_processor import load_product_images
    for p in products:
        load_product_images(p)

    # ── 3. 连接浏览器 ─────────────────────────────────────────────────────────
    logger.info('=== 连接已有浏览器 (CDP:9222) ===')
    from core.browser import BrowserEngine
    engine = BrowserEngine(account_name='taobao')
    page = await engine.start()
    logger.info(f'  当前页面: {page.url}')

    # ── 4. 逐个上架 ───────────────────────────────────────────────────────────
    logger.info('=== 开始上架 ===')
    from core.uploader import TaobaoUploader
    uploader = TaobaoUploader(engine)
    # dry_run 默认 False，会真实点击发布按钮

    results = []
    for product in products:
        product.shipping_tpl = SHIPPING_TPL
        logger.info(f'[{product.seq}] 开始上架: {product.title[:40]}')
        try:
            success = await uploader.upload(product)
        except Exception as e:
            product.error = str(e)
            success = False
        results.append((product, success))
        if success:
            logger.success(f'[{product.seq}] 上架成功  商品ID={product.item_id}')
        else:
            logger.error(f'[{product.seq}] 上架失败: {product.error}')

    # ── 5. 汇总 ──────────────────────────────────────────────────────────────
    ok  = [r for r in results if r[1]]
    err = [r for r in results if not r[1]]
    logger.info('=' * 50)
    logger.info(f'完成  成功 {len(ok)}/{len(results)} 个')
    for p, _ in ok:
        logger.success(f'  [{p.seq}] {p.title[:30]}  ID={p.item_id}')
    for p, _ in err:
        logger.error(f'  [{p.seq}] {p.title[:30]}  错误={p.error}')
    logger.info(f'日志已保存: {log_path}')

    await engine.close()


if __name__ == '__main__':
    asyncio.run(main())
