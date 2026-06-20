"""
主调度器：多店铺分发 + 批量控频 + 断点续传 + 报告生成。
"""
import asyncio
import random
from pathlib import Path
from loguru import logger

from core.browser import BrowserEngine
from core.uploader import TaobaoUploader
from core.task_queue import TaskQueue
from core.account_manager import AccountManager, Account
from core.data_reader import read_excel, attach_images
from core.reporter import generate_report
from models.product import Product, TaskStatus

_BATCH_SIZE  = 20    # 每批商品数，批后休息
_BATCH_BREAK = (180, 480)   # 批间休息秒数范围
_PRODUCT_GAP = (30, 90)     # 商品间隔秒数范围


class Scheduler:
    def __init__(self, excel_path: str, data_root: str | None = None):
        self._excel_path = Path(excel_path)
        self._data_root  = Path(data_root) if data_root else self._excel_path.parent
        self._accounts   = AccountManager()
        self._queue: TaskQueue | None = None
        self._engines: dict[str, BrowserEngine] = {}
        self._stop_flag  = False

    # ── 公开入口 ───────────────────────────────────────────────────────────

    async def run(self):
        # 若 GUI 已预先加载商品并设置了 _queue，直接使用，跳过文件读取
        if self._queue is None:
            p = self._excel_path
            if p.is_dir():
                from core.data_reader import scan_and_read_folder
                products = scan_and_read_folder(p)
            else:
                products = read_excel(p)
                attach_images(products, self._data_root)
            self._queue = TaskQueue(products)
        else:
            products = self._queue._products

        pending = self._queue.pending()

        if not pending:
            logger.info("没有待处理商品，任务结束")
            generate_report(products)
            return

        logger.info(f"共 {len(pending)} 个商品待上架，开始执行…")

        try:
            await self._run_all(pending)
        finally:
            await self._close_all_engines()
            self._queue.save_state()
            generate_report(products)
            s = self._queue.summary()
            logger.info(f"全部完成  ✅{s['done']}  ❌{s['failed']}  ⏳{s['pending']}")

    # ── 批量调度 ───────────────────────────────────────────────────────────

    async def _run_all(self, pending: list[Product]):
        batch_count = 0

        for product in pending:
            if self._stop_flag or self._queue.is_cancelled:
                logger.warning("调度器收到停止信号，退出")
                break

            # 等待暂停解除
            while self._queue.is_paused:
                await asyncio.sleep(2)

            # 选择可用账号
            account = self._accounts.get_available()
            if account is None:
                logger.warning("所有账号今日上架已达上限，任务停止")
                break

            # 获取/启动该账号的浏览器
            engine = await self._get_engine(account)
            if engine is None:
                product.status = TaskStatus.FAILED
                product.error  = '浏览器启动失败'
                continue

            # 检查引擎是否被安全弹窗停止
            if engine._stop_flag:
                logger.error(f"账号 [{account.label}] 已触发安全停止，跳过")
                product.status = TaskStatus.SKIPPED
                continue

            # 执行上架
            uploader = TaobaoUploader(engine)
            # 将运费模板名映射为该账号实际名称
            product.shipping_tpl = self._accounts.resolve_shipping_tpl(
                account, product.shipping_tpl
            )
            success = await uploader.upload(product)

            if success:
                account.increment()
                self._accounts.save_counters()

            self._queue.save_state()   # 每个商品完成后持久化

            batch_count += 1
            if batch_count % _BATCH_SIZE == 0:
                gap = random.uniform(*_BATCH_BREAK)
                logger.info(f"已完成 {batch_count} 个商品，休息 {gap:.0f} 秒…")
                await asyncio.sleep(gap)
            else:
                gap = random.uniform(*_PRODUCT_GAP)
                logger.debug(f"商品间隔 {gap:.0f} 秒")
                await asyncio.sleep(gap)

    # ── 浏览器引擎管理 ────────────────────────────────────────────────────

    async def _get_engine(self, account: Account) -> BrowserEngine | None:
        if account.name in self._engines:
            eng = self._engines[account.name]
            if not eng._stop_flag:
                return eng
            # 已停止的引擎关闭后重置
            await eng.close()
            del self._engines[account.name]

        try:
            eng = BrowserEngine(
                account_name=account.name,
                profiles_root='profiles'
            )
            # 安全停止回调：通知调度器
            original_on_security = eng._on_security
            async def on_security_with_scheduler():
                await original_on_security()
                logger.error(f"账号 [{account.label}] 安全风控，该账号停用")
            eng._on_security = on_security_with_scheduler

            await eng.start()
            self._engines[account.name] = eng
            logger.info(f"账号 [{account.label}] 浏览器已启动")
            return eng
        except Exception as e:
            logger.error(f"账号 [{account.name}] 浏览器启动失败: {e}")
            return None

    async def _close_all_engines(self):
        for name, eng in self._engines.items():
            try:
                await eng.close()
                logger.info(f"账号 [{name}] 浏览器已关闭")
            except Exception:
                pass
        self._engines.clear()

    # ── 外部控制 ───────────────────────────────────────────────────────────

    def pause(self):
        if self._queue:
            self._queue.pause()

    def resume(self):
        if self._queue:
            self._queue.resume()

    def stop(self):
        self._stop_flag = True
        if self._queue:
            self._queue.cancel()
