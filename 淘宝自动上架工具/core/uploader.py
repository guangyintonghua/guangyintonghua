"""
淘宝商品发布 v2 版本上架主流程。

关键经验（2026-06-12 人工上架审查总结）：
  1. React 表单  fill() 不触发 onChange，必须用 execCommand('insertText')
  2. SKU 价格    须在所有其他字段操作完成后最后填写（React 重渲染会清空）
  3. 规格添加    使用内联 "+ 添加颜色"/"+ 添加规格" 按钮（无弹窗对话框）
  4. 多件优惠    复选框可能 disabled，需判断跳过
  5. catId 直链  URL 携带 catId 参数可跳过类目选择弹窗
  6. 属性字段    标签类名 info-wrapper-label（非 prop），需按标签文字定位
  7. 图片上传    CDP 模式 expect_file_chooser 不可用；用 JS 钩子拦截 file input
  8. 运费模板    next-select 组件，按标签文字定位行；默认已选时可跳过
"""
import asyncio
import re
import time
from pathlib import Path
from loguru import logger
from playwright.async_api import Page, TimeoutError as PWTimeout

from core.browser import BrowserEngine
from core.human_behavior import HumanBehavior
from core.image_processor import load_product_images
from models.product import Product, TaskStatus

_PUBLISH_URL = 'https://item.upload.taobao.com/sell/v2/publish.htm?catId={cat_id}'
_DEFAULT_CAT_ID = '121458013'   # 居家布艺>>餐桌布艺>>桌布


def _truncate_title(title: str, limit: int = 60) -> str:
    count = 0
    for i, ch in enumerate(title):
        count += 2 if '一' <= ch <= '鿿' else 1
        if count > limit:
            return title[:i]
    return title


class TaobaoUploader:
    def __init__(self, engine: BrowserEngine):
        self.engine       = engine
        self.page:   Page          = engine.page
        self.human:  HumanBehavior = engine.human
        self._current_seq: str = ''
        self.dry_run: bool = False   # True=填好表单后不点发布，等用户手动确认

    def _step(self, msg: str):
        """向GUI发送步骤进度（格式: 〔步骤:seq〕消息）"""
        logger.info(f'〔步骤:{self._current_seq}〕{msg}')

    # ── 公开入口 ───────────────────────────────────────────────────────────

    async def upload(self, product: Product) -> bool:
        self._current_seq = str(product.seq)
        product.status = TaskStatus.RUNNING
        logger.info(f"[{product.seq}] 开始上架: {product.title[:30]!r}")

        if product.title_char_count > 60:
            product.title = _truncate_title(product.title, 60)
            logger.warning(f"[{product.seq}] 标题超长已自动截断: {product.title!r}")

        load_product_images(product)

        if not product.main_images:
            product.status = TaskStatus.FAILED
            product.error  = '无主图：淘宝必须上传至少1张主图，请检查图片文件夹'
            logger.error(f"[{product.seq}] 无主图，终止上架（淘宝必填项）")
            return False

        try:
            self._step('导航')
            await self._navigate_to_publish(product.cat_id or _DEFAULT_CAT_ID)
            if not await self._ok(): return False

            self._step('标题')
            await self._fill_title(product.title)
            if not await self._ok(): return False

            if product.guide_title:
                self._step('导购标题')
                await self._fill_guide_title(product.guide_title)
                if not await self._ok(): return False

            await self._upload_main_images(product)
            if not await self._ok(): return False

            if product.main_images_3x4:
                self._step('3:4主图')
                await self._upload_main_images_3x4(product)
                if not await self._ok(): return False

            if product.white_bg_images:
                self._step('白底图')
                await self._upload_white_bg_image(product)
                if not await self._ok(): return False

            if product.selling_images:
                self._step('卖点图')
                await self._upload_selling_images(product)
                if not await self._ok(): return False

            if product.detail_images:
                self._step('详情图')
                await self._upload_detail_images(product)
                if not await self._ok(): return False

            self._step('属性')
            await self._fill_attributes(product.attributes)
            if not await self._ok(): return False

            self._step('规格')
            await self._fill_sku_specs(product)
            if not await self._ok(): return False

            self._step('物流')
            await self._fill_shipping(product.shipping_tpl, product.delivery_days)
            if not await self._ok(): return False

            self._step('价格')
            # 先填价格/库存（多件优惠「启用」checkbox 需要先有价格才可点击）
            await self._fill_sku_prices(product)
            if not await self._ok(): return False

            # 再启用多件优惠（此时价格已存在，启用 checkbox 应为可点击状态）
            await self._enable_multi_discount(
                product.multi_discount_enabled,
                product.multi_discount_rate,
            )
            if not await self._ok(): return False

            self._step('提交')
            item_id = await self._submit()
            if item_id:
                product.item_id = item_id
                product.status  = TaskStatus.DONE
                logger.success(f"[{product.seq}] 上架成功  商品ID={item_id}")
                return True

            product.status = TaskStatus.FAILED
            product.error  = '提交后未获取到商品ID'
            return False

        except Exception as e:
            product.status = TaskStatus.FAILED
            product.error  = str(e)
            logger.exception(f"[{product.seq}] 上架异常: {e}")
            await self._screenshot(f"error_{product.seq}")
            return False

    # ── Step1: 直链导航 ────────────────────────────────────────────────────

    async def _navigate_to_publish(self, cat_id: str):
        url = _PUBLISH_URL.format(cat_id=cat_id)
        logger.debug(f"导航到发布页: {url}")

        if 'publish.htm' in self.page.url:
            logger.debug("已在发布页，重载以清空表单")

            # 先 CDP dismiss 任何残留的 native beforeunload 对话框
            # （上次 reload 超时后对话框可能仍在显示，导致后续 goto 被 ERR_ABORTED）
            try:
                _pre_client = await self.page.context.new_cdp_session(self.page)
                await _pre_client.send('Page.enable')
                await _pre_client.send('Page.handleJavaScriptDialog', {'accept': True})
                await asyncio.sleep(0.3)
                logger.debug("  已 dismiss 残留 beforeunload 对话框")
            except Exception:
                pass  # 没有对话框时 handleJavaScriptDialog 会抛出 → 忽略
            finally:
                try:
                    await _pre_client.detach()
                except Exception:
                    pass

            # 再关闭可见抽屉/弹窗（UI 层面，不强制移除 DOM）
            await self._force_close_all_overlays(force_remove=False)

            reloaded = False
            client = None
            try:
                client = await self.page.context.new_cdp_session(self.page)
                # 必须先 Page.enable 才能接收 Page.javascriptDialogOpening 事件
                await client.send('Page.enable')

                async def _auto_accept_dialog(params):
                    logger.debug(f"  CDP dialog: {params.get('type')} → accept")
                    try:
                        await client.send('Page.handleJavaScriptDialog', {'accept': True})
                    except Exception as _e:
                        logger.debug(f"  handleDialog 失败: {_e}")

                client.on('Page.javascriptDialogOpening', _auto_accept_dialog)

                # JS 层三重禁用 beforeunload（与 CDP 双保险）
                await self.page.evaluate("""() => {
                    try {
                        window.onbeforeunload = null;
                        // 1. BeforeUnloadEvent.returnValue setter noop → 阻止 handlers 激活弹窗
                        Object.defineProperty(BeforeUnloadEvent.prototype, 'returnValue', {
                            get() { return ''; },
                            set(_v) {},
                            configurable: true
                        });
                        // 2. dispatchEvent 劫持 → 拦截 beforeunload 事件本身
                        const _origDispatch = EventTarget.prototype.dispatchEvent;
                        EventTarget.prototype.dispatchEvent = function(ev) {
                            if (ev && ev.type === 'beforeunload') return true;
                            return _origDispatch.call(this, ev);
                        };
                    } catch(e) {}
                }""")

                try:
                    await self.page.reload(wait_until='domcontentloaded', timeout=25000)
                    reloaded = True
                    logger.debug("  页面重载成功")
                except Exception as e1:
                    logger.warning(f"  reload 失败: {e1}，dismiss 对话框后 goto")
                    # reload 超时后可能有新的 beforeunload 对话框 → 先 dismiss
                    try:
                        await client.send('Page.handleJavaScriptDialog', {'accept': True})
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
                    try:
                        await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        reloaded = True
                        logger.debug("  goto 导航成功")
                    except Exception as e2:
                        logger.warning(f"  goto 也失败: {e2}")
            except Exception as e_cdp:
                logger.warning(f"  CDP session 失败: {e_cdp}")
            finally:
                if client:
                    try:
                        await client.detach()
                    except Exception:
                        pass

            if not reloaded:
                logger.warning("  导航失败，清空 backdrop 继续（React 状态可能不完整）")
                await self._force_close_all_overlays(force_remove=True)
        else:
            await self.engine.goto(url, wait='domcontentloaded')

        try:
            await self.page.wait_for_selector(
                'input[placeholder*="30个汉字"], textarea[placeholder*="标题"]',
                timeout=25000,
            )
        except PWTimeout:
            logger.warning("标题输入框等待超时（25s），继续执行")
        await self.human.pause(1.5, 2.5)

    # ── Step2: 填写标题 ────────────────────────────────────────────────────

    async def _fill_title(self, title: str):
        logger.debug("填写标题…")
        inp = self.page.locator(
            'input[placeholder*="30个汉字"], '
            'textbox[placeholder*="30个汉字"], '
            'input[placeholder*="60字符"]'
        ).first
        await inp.click()
        await self._react_fill(inp, title)
        await self.human.between_fields()
        logger.debug(f"标题已填: {title[:20]}…")

    # ── Step2b: 填写导购标题 ───────────────────────────────────────────────

    async def _fill_guide_title(self, guide_title: str):
        if not guide_title:
            return
        # 截断：每个汉字算2个字符，总限30字符
        truncated = _truncate_title(guide_title, 30)
        inp = self.page.locator(
            'input[placeholder*="15个汉字"], '
            'input[placeholder*="导购标题"], '
            'input[placeholder*="短标题"]'
        ).first
        if not await inp.count():
            logger.debug("未找到导购标题输入框，跳过")
            return
        await inp.click()
        await self._react_fill(inp, truncated)
        await self.human.between_fields()
        logger.debug(f"导购标题已填: {truncated!r}")

    # ── 辅助：素材选择器 iframe 图片上传 ─────────────────────────────────

    async def _get_sucai_frame(self, frame_name: str = 'mainImagesGroup'):
        """等待并返回素材选择器 iframe 的 Frame 对象（最多等40秒，网络慢时库打开需20+秒）"""
        for _ in range(80):
            for f in self.page.frames:
                url = f.url
                if 'sucai-selector' in url:
                    return f
                if f.name == frame_name and url not in ('', 'about:blank', 'about:srcdoc'):
                    return f
            await asyncio.sleep(0.5)
        return None

    async def _install_file_hook_in_frame(self, frame):
        """在指定 frame 中安装 file input 拦截钩子"""
        await frame.evaluate("""() => {
            if (window._tbFileHook) return;
            window._tbFileHook = true;
            window._tbFilePending = null;
            const orig = HTMLInputElement.prototype.click;
            window._tbOrigClick = orig;  // 保存原始 click 以便 expect_file_chooser 时恢复
            HTMLInputElement.prototype.click = function() {
                if (this.type === 'file') {
                    if (!this.id) this.id = '_tbf_' + Date.now();
                    window._tbFilePending = this.id;
                    return;
                }
                return orig.call(this);
            };
        }""")

    async def _upload_via_sucai_iframe(self, img_path: Path, i: int) -> bool:
        """主图上传：确保无残留overlay → 点击空槽 → sucai iframe 选图"""
        # 先清理可能残留的 overlay，防止拦截槽位点击
        if await self.page.locator('.next-overlay-wrapper.opened').count():
            logger.debug(f"  主图 {i+1}: 发现残留overlay，先强制关闭")
            await self._force_close_sucai_overlay()
            await asyncio.sleep(0.5)

        # 找空槽位
        section = await self._get_image_section('1:1主图')
        if section is None:
            section = self.page.locator('div.sell-component-simply-images').first
        if not await section.count():
            return False

        slot = section.locator('div.image-empty').first
        if not await slot.count():
            logger.warning(f"  主图 {i+1}: 无更多空槽位")
            return False

        await slot.scroll_into_view_if_needed()
        await slot.click()
        await asyncio.sleep(4.0)   # 网络慢时 sucai 需要更多时间初始化

        # 等待 sucai iframe 出现
        sucai_frame = await self._get_sucai_frame()
        if sucai_frame is None:
            # 重试：关闭可能残留的 overlay，重新点击槽位
            logger.debug(f"  主图 {i+1}: iframe 未出现，关闭残留 overlay 后重试")
            await self._force_close_sucai_overlay()
            await asyncio.sleep(2.0)
            slot2 = section.locator('div.image-empty').first
            if await slot2.count():
                await slot2.scroll_into_view_if_needed()
                await slot2.click()
                await asyncio.sleep(4.0)
                sucai_frame = await self._get_sucai_frame()

        if sucai_frame is None:
            logger.warning(f"  主图 {i+1}: 素材选择器 iframe 未出现")
            return False

        ok = await self._select_from_sucai(sucai_frame, img_path, f"主图{i+1}")
        if ok:
            return True

        # 首次失败：图片已入库但在上传标签页无法通过touch选中（realtime模式无footer兜底）
        # 关闭sucai重新打开，此时图片已在library，走library路径可成功
        logger.debug(f"  主图 {i+1}: 首次失败，重开sucai走library路径重试")
        await asyncio.sleep(2.0)
        slot_retry = section.locator('div.image-empty').first
        if not await slot_retry.count():
            logger.warning(f"  主图 {i+1}: 重试时无空槽位（图片可能已成功入槽）")
            return False
        await slot_retry.scroll_into_view_if_needed()
        await slot_retry.click()
        await asyncio.sleep(2.5)
        sucai_frame2 = await self._get_sucai_frame()
        if sucai_frame2 is None:
            logger.warning(f"  主图 {i+1}: 重试时sucai iframe未出现")
            return False
        return await self._select_from_sucai(sucai_frame2, img_path, f"主图{i+1}重试")

    async def _wait_sucai_frame_close(self, timeout_ms: int = 10000) -> bool:
        """等待 sucai 选择器 iframe 从 page.frames 消失（自动关闭意味着选图成功）"""
        steps = timeout_ms // 200
        for _ in range(steps):
            still_open = any(
                'sucai-selector' in f.url
                or (f.name == 'mainImagesGroup' and f.url not in ('', 'about:blank'))
                for f in self.page.frames
            )
            if not still_open:
                return True
            await asyncio.sleep(0.2)
        return False

    async def _force_close_sucai_overlay(self):
        """强制关闭所有 sucai 覆盖层（Escape + 清空iframe src + 隐藏overlay，保留DOM）"""
        await self.page.keyboard.press('Escape')
        await asyncio.sleep(0.3)
        try:
            backdrop = self.page.locator(
                '.next-overlay-wrapper.opened .next-overlay-backdrop'
            ).first
            if await backdrop.count():
                await backdrop.click(force=True)
                await asyncio.sleep(0.2)
        except Exception:
            pass
        # 保留 iframe DOM 节点（维持 React fiber 完整性），只清空 src 使其从 page.frames 消失
        n = await self.page.evaluate("""() => {
            let n = 0;
            document.querySelectorAll('.next-overlay-wrapper').forEach(el => {
                el.querySelectorAll('iframe').forEach(f => {
                    f.src = 'about:blank';  // 清空内容但保留 DOM 节点
                });
                el.classList.remove('opened');
                el.style.display = 'none';
                n++;
            });
            return n;
        }""")
        if n:
            logger.debug(f"  JS强制隐藏overlay {n} 个（iframe src已清空）")
        await asyncio.sleep(0.4)
        # 等旧 sucai frame URL 变为 about:blank（不再检查 name，Playwright 缓存旧 name）
        for _ in range(10):
            if not any('sucai-selector' in f.url for f in self.page.frames):
                break
            await asyncio.sleep(0.3)

    async def _find_sucai_item(self, sucai_frame, img_name: str):
        """在sucai库中找到指定文件名的图片条目，返回Locator或None"""
        pat = re.compile(r'^' + re.escape(img_name) + r'$', re.IGNORECASE)
        item = sucai_frame.locator('[class*="PicList_PicturesShow_main-show"]').filter(
            has=sucai_frame.locator('[class*="PicList_tip_title"]').filter(has_text=pat)
        )
        if await item.count():
            return item.first
        stem = Path(img_name).stem
        item = sucai_frame.locator('[class*="PicList_PicturesShow_main-show"]').filter(
            has=sucai_frame.locator('[class*="PicList_tip_title"]').filter(
                has_text=re.compile(r'^' + re.escape(stem), re.IGNORECASE)
            )
        )
        return item.first if await item.count() else None

    # ── sucai postMessage 监听（关键：needClose=false，靠msg判定选图成功）───────

    async def _install_sucai_msg_listener(self):
        """在父页面注入sucai postMessage监听器（needClose=false时靠msg判定成功）"""
        await self.page.evaluate("""() => {
            window.__sucai_received = null;
            if (window.__sucai_msg_handler) {
                window.removeEventListener('message', window.__sucai_msg_handler);
            }
            window.__sucai_msg_handler = function(ev) {
                let data = ev.data;
                if (typeof data === 'string') {
                    try { data = JSON.parse(data); } catch(e) { return; }
                }
                if (data && typeof data === 'object' && data.type === 'sucai') {
                    window.__sucai_received = data;
                }
            };
            window.addEventListener('message', window.__sucai_msg_handler);
        }""")

    async def _clear_sucai_msg(self):
        """清除已接收的sucai postMessage标志"""
        await self.page.evaluate("() => { window.__sucai_received = null; }")

    async def _wait_sucai_msg(self, handle_id: str | None, timeout_ms: int = 5000) -> bool:
        """等待sucai发送postMessage到父页面，或sucai自动关闭（均视为图片被接受）"""
        steps = timeout_ms // 200
        for _ in range(steps):
            # 方式1: postMessage
            received = await self.page.evaluate("() => window.__sucai_received || null")
            if received:
                hid = received.get('handleId') if isinstance(received, dict) else None
                if not handle_id or hid == handle_id:
                    obj_count = len(received.get('obj', [])) if isinstance(received, dict) else 0
                    logger.debug(f"  sucai: 收到postMessage handleId={hid} obj={obj_count}张")
                    return True
            # 方式2: sucai auto-close（部分sucai直接关闭不发msg）
            still_open = any('sucai-selector' in f.url for f in self.page.frames)
            if not still_open:
                logger.debug(f"  sucai: auto-closed（无postMessage）")
                return True
            await asyncio.sleep(0.2)
        return False

    async def _get_sucai_handle_id(self, sucai_frame) -> str | None:
        """从sucai iframe URL提取handleId参数"""
        url = sucai_frame.url
        for part in url.split('&'):
            if part.startswith('handleId='):
                return part.split('=', 1)[1]
        return None

    async def _click_sucai_image(self, sucai_frame, img_name: str) -> bool:
        """找到并选中sucai库图片（realtime模式→选中自动关闭）

        核心经验：
        - realtime模式无footer按钮，选中后sucai自动关闭
        - sucai是移动端React应用，需要touchstart/touchend事件，不响应普通mouse click
        - JS内可dispatch TouchEvent（不受Playwright hasTouch限制）
        - aria-checked=true是上次残留状态，需先发touch deselect再select
        """
        item = await self._find_sucai_item(sucai_frame, img_name)
        if item is None:
            return False

        await item.scroll_into_view_if_needed()
        img_stem = Path(img_name).stem

        # 策略A: JS TouchEvent（移动端React app的真正触发方式）
        try:
            result = await sucai_frame.evaluate("""(stemName) => {
                const items = document.querySelectorAll('[class*="PicList_PicturesShow_main-show"]');
                for (const item of items) {
                    const title = item.querySelector('[class*="PicList_tip_title"]');
                    if (!title) continue;
                    const text = (title.textContent || '').toLowerCase();
                    if (!text.includes(stemName.toLowerCase())) continue;

                    const target = item.querySelector('label') || item;
                    const rect = target.getBoundingClientRect();
                    if (rect.width === 0) continue;
                    const cx = rect.left + rect.width / 2;
                    const cy = rect.top + rect.height / 2;

                    function fire(el, type) {
                        try {
                            const t = new Touch({
                                identifier: Date.now() + Math.random(),
                                target: el,
                                clientX: cx, clientY: cy,
                                screenX: cx, screenY: cy,
                                pageX: cx + window.scrollX,
                                pageY: cy + window.scrollY,
                                radiusX: 10, radiusY: 10, rotationAngle: 0, force: 1
                            });
                            el.dispatchEvent(new TouchEvent(type, {
                                bubbles: true, cancelable: true,
                                touches: type === 'touchend' ? [] : [t],
                                changedTouches: [t], targetTouches: type === 'touchend' ? [] : [t]
                            }));
                            return true;
                        } catch(e) { return false; }
                    }

                    const input = item.querySelector('input[type="checkbox"]');
                    const alreadyChecked = input && (input.checked ||
                        input.getAttribute('aria-checked') === 'true');

                    if (alreadyChecked) {
                        // 先取消选中（deselect）
                        fire(target, 'touchstart');
                        fire(target, 'touchend');
                    }
                    // 选中
                    fire(target, 'touchstart');
                    fire(target, 'touchend');
                    return alreadyChecked ? 'desel+sel' : 'select';
                }
                return null;
            }""", img_stem)
            logger.debug(f"  sucai: A策略(touch)={result}")
            if result:
                await asyncio.sleep(1.2)
                if not any('sucai-selector' in f.url for f in self.page.frames):
                    logger.debug(f"  sucai: A策略touch触发realtime关闭")
                    return True
                if await self._is_sucai_footer_enabled(sucai_frame):
                    logger.debug(f"  sucai: A策略touch启用footer")
                    return True
        except Exception as e:
            logger.debug(f"  sucai A策略失败: {e}")

        # 策略B: Playwright click（trusted CDP mouse events，作为touch备用）
        try:
            label = item.locator('label').first
            target = label if await label.count() else item
            # 如果已选中，先click一次取消选中
            cb = item.locator('input[type="checkbox"]').first
            if await cb.count() and await cb.is_checked():
                await target.click(force=True)
                await asyncio.sleep(0.5)
            # 选中
            await target.click(force=True)
            await asyncio.sleep(1.0)
            if not any('sucai-selector' in f.url for f in self.page.frames):
                logger.debug(f"  sucai: B策略(click)realtime关闭")
                return True
            if await self._is_sucai_footer_enabled(sucai_frame):
                logger.debug(f"  sucai: B策略(click)footer启用")
                return True
        except Exception as e:
            logger.debug(f"  sucai B策略失败: {e}")

        # 策略C: 直接force点footer（多选模式下的备用）
        try:
            footer_btn = sucai_frame.locator('[class*="Footer_selectOk"]').first
            if await footer_btn.count():
                await footer_btn.click(force=True)
                await asyncio.sleep(1.0)
                if not any('sucai-selector' in f.url for f in self.page.frames):
                    logger.debug(f"  sucai: C策略(footer)关闭")
                    return True
        except Exception as e:
            logger.debug(f"  sucai C策略失败: {e}")

        logger.debug(f"  sucai: 所有策略均未选中 {img_name!r}")
        return False

    async def _is_sucai_footer_enabled(self, sucai_frame) -> bool:
        """检查sucai Footer确认按钮是否已启用（=图片已选中）"""
        try:
            btn = sucai_frame.locator('[class*="Footer_selectOk"]')
            if await btn.count():
                return await btn.first.is_enabled()
        except Exception:
            pass
        return False

    async def _click_sucai_footer_ok(self, sucai_frame) -> bool:
        """点击sucai Footer已启用的完成/确定按钮，返回是否成功"""
        await asyncio.sleep(0.3)
        # 优先: Footer_selectOk 且未禁用
        try:
            btn = sucai_frame.locator('[class*="Footer_selectOk"]:not([disabled])')
            if await btn.count():
                await btn.first.click(force=True)
                logger.debug(f"  sucai Footer_selectOk 已点击")
                return True
        except Exception:
            pass
        # 备用: Footer区域任意启用按钮
        try:
            btn = sucai_frame.locator('[class*="Footer"] button:not([disabled])')
            if await btn.count():
                txt = await btn.first.inner_text()
                if any(k in txt for k in ['完成', '确定', '确认', 'OK', '选择']):
                    await btn.first.click(force=True)
                    logger.debug(f"  sucai Footer备用按钮: [{txt.strip()[:6]}]")
                    return True
        except Exception:
            pass
        return False

    async def _select_from_sucai(self, sucai_frame, img_path: Path, label: str) -> bool:
        """
        在已打开的素材选择器中选图。

        两种sucai模式：
        1. realTimeSel模式（主图）：点img缩略图 → 立即发postMessage → 父页放槽 → 手动关闭
        2. 非realTimeSel模式（详情图）：点img → footer按钮启用 → 点footer → 发postMessage → 关闭

        共同收尾：收到postMessage 或 sucai自动关闭 均视为成功。
        """
        # 智能等待库加载：有图片立刻继续，没有则最多再等15s
        _item_sel = '[class*="PicList_PicturesShow_main-show"]'
        _has_items = await sucai_frame.locator(_item_sel).count() > 0
        if _has_items:
            logger.debug(f"  {label}: sucai库已有图片，直接开始")
        else:
            logger.debug(f"  {label}: sucai库暂无图片，等待加载（最多15s）...")
            for _w in range(30):   # 15s
                await asyncio.sleep(0.5)
                if await sucai_frame.locator(_item_sel).count() > 0:
                    logger.debug(f"  {label}: sucai库图片已出现（等了{(_w+1)*0.5:.1f}s）")
                    break
            else:
                logger.debug(f"  {label}: sucai库15s内无图片，走本地上传路径")

        handle_id = await self._get_sucai_handle_id(sucai_frame)
        sucai_url_short = sucai_frame.url[:150]
        logger.debug(f"  {label}: sucai URL={sucai_url_short}")
        await self._install_sucai_msg_listener()
        await self._clear_sucai_msg()

        # A: 库中已有图
        item = await self._find_sucai_item(sucai_frame, img_path.name)
        if item:
            logger.debug(f"  {label}: 库中找到 {img_path.name!r}，用_click_sucai_image选图")
            await self._clear_sucai_msg()
            # 使用_click_sucai_image（含deselect+3策略），处理aria-checked残留问题
            clicked = await self._click_sucai_image(sucai_frame, img_path.name)
            logger.debug(f"  {label}: 等待postMessage/footer/auto-close (handleId={handle_id})")

            for _ in range(100):  # 20s（upload-tab状态图片响应慢，需要更长等待）
                # 方式1: postMessage (realTimeSel模式，主图sucai)
                received = await self.page.evaluate("() => window.__sucai_received || null")
                if received:
                    hid = received.get('handleId') if isinstance(received, dict) else None
                    if not handle_id or hid == handle_id:
                        logger.debug(f"  {label}: 库选图postMessage收到，图片已入槽")
                        await asyncio.sleep(0.8)
                        await self._force_close_sucai_overlay()
                        return True
                # 方式2: sucai auto-close
                if not any('sucai-selector' in f.url for f in self.page.frames):
                    logger.debug(f"  {label}: sucai auto-closed，视为成功")
                    return True
                # 方式3: footer按钮启用（非realTimeSel模式，详情图sucai）
                if await self._is_sucai_footer_enabled(sucai_frame):
                    logger.debug(f"  {label}: footer已启用，点击确认")
                    await self._clear_sucai_msg()
                    await self._click_sucai_footer_ok(sucai_frame)
                    await asyncio.sleep(0.5)
                    if await self._wait_sucai_msg(handle_id, timeout_ms=8000):
                        logger.debug(f"  {label}: footer后postMessage/close收到，成功")
                        if any('sucai-selector' in f.url for f in self.page.frames):
                            await self._force_close_sucai_overlay()
                        return True
                    logger.debug(f"  {label}: footer已点但未收msg，视为成功并关闭")
                    await self._force_close_sucai_overlay()
                    return True
                await asyncio.sleep(0.2)
            logger.debug(f"  {label}: 库图6s内无响应，改用本地上传")

        # B: 库中无图 或 库图未响应 → 本地上传
        logger.debug(f"  {label}: 本地上传 {img_path.name!r}")
        await self._clear_sucai_msg()

        # 优先：直接找 input[type="file"] 设置文件（绕过 file chooser 对话框）
        file_inputs = await sucai_frame.locator('input[type="file"]').all()
        logger.debug(f"  {label}: 找到 {len(file_inputs)} 个file input")
        if file_inputs:
            fi = file_inputs[-1]
            await fi.set_input_files(str(img_path))
            logger.debug(f"  {label}: set_input_files完成（直接input），等待上传（最多90s）")
        else:
            # 备用：点击「本地上传」按钮（或tab）再通过hook捕获input
            await self._install_file_hook_in_frame(sucai_frame)
            await sucai_frame.evaluate("() => { window._tbFilePending = null; }")

            async def _find_upload_btn(frame):
                """多策略查找本地上传按钮/tab"""
                for pat in [
                    r'本地上传',
                    r'上传图片',
                    r'上传本地',
                    r'上传',
                ]:
                    # 优先 primary 按钮
                    b = frame.locator('button.next-btn-primary, button.next-btn').filter(
                        has_text=re.compile(pat)
                    ).first
                    if await b.count():
                        return b
                    # role=tab / div tab
                    b = frame.locator('[role="tab"], [class*="tab-item"], [class*="TabItem"]').filter(
                        has_text=re.compile(pat)
                    ).first
                    if await b.count():
                        return b
                    # generic get_by_role
                    b = frame.get_by_role('button', name=re.compile(pat)).first
                    if await b.count():
                        return b
                return None

            local_btn = await _find_upload_btn(sucai_frame)
            upload_btn_set = False  # 标志：是否已通过file input直接上传（不需要再点按钮）
            if not local_btn:
                # 等待最多8s让sucai完全渲染
                for _ in range(16):
                    await asyncio.sleep(0.5)
                    local_btn = await _find_upload_btn(sucai_frame)
                    if local_btn:
                        break
                    # 也检查是否直接出现了 file input
                    extra_fi = await sucai_frame.locator('input[type="file"]').all()
                    if extra_fi:
                        await extra_fi[-1].set_input_files(str(img_path))
                        logger.debug(f"  {label}: 等待后出现 file input，直接上传")
                        upload_btn_set = True
                        break

            if not local_btn and not upload_btn_set:
                # 还是找不到：JS暴力寻找并点击任何可能的上传触发器
                clicked_js = await sucai_frame.evaluate("""() => {
                    const texts = ['本地上传', '上传图片', '上传', 'upload'];
                    for (const el of document.querySelectorAll('button, [role="tab"], [class*="tab"]')) {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (texts.some(x => t.includes(x))) {
                            el.click(); return t;
                        }
                    }
                    return null;
                }""")
                if clicked_js:
                    logger.debug(f"  {label}: JS点击上传触发器 {clicked_js!r}")
                    await asyncio.sleep(0.8)
                    extra_fi = await sucai_frame.locator('input[type="file"]').all()
                    if extra_fi:
                        await extra_fi[-1].set_input_files(str(img_path))
                        logger.debug(f"  {label}: JS点击后找到file input，上传")
                        upload_btn_set = True
                    else:
                        logger.warning(f"  {label}: 找不到file input和本地上传按钮，强制关闭")
                        await self._force_close_sucai_overlay()
                        return False
                else:
                    logger.warning(f"  {label}: 找不到file input和本地上传按钮，强制关闭")
                    await self._force_close_sucai_overlay()
                    return False

            if local_btn and not upload_btn_set:
                try:
                    await local_btn.click(timeout=5000, force=True)
                except Exception:
                    await local_btn.evaluate("el => el.click()")

                # 等待 file input 出现（最多3s），hook 的 _tbFilePending 或直接 input[type=file]
                file_sent = False
                for _w in range(15):  # 3s
                    await asyncio.sleep(0.2)
                    inp_id = await sucai_frame.evaluate(
                        "() => { const id=window._tbFilePending; window._tbFilePending=null; return id; }"
                    )
                    if inp_id:
                        loc = sucai_frame.locator(f'#{inp_id}')
                        if await loc.count():
                            await loc.set_input_files(str(img_path))
                        else:
                            all_fi = await sucai_frame.locator('input[type="file"]').all()
                            if all_fi:
                                await all_fi[-1].set_input_files(str(img_path))
                        file_sent = True
                        break
                    all_fi = await sucai_frame.locator('input[type="file"]').all()
                    if all_fi:
                        await all_fi[-1].set_input_files(str(img_path))
                        file_sent = True
                        break

                if not file_sent:
                    # 最后兜底：恢复原始 click → 用 expect_file_chooser 等待原生文件对话框
                    logger.debug(f"  {label}: hook未捕获file input，尝试 expect_file_chooser")
                    try:
                        # 先恢复原始 input.click 以允许浏览器弹出文件对话框
                        await sucai_frame.evaluate("""() => {
                            if (window._tbOrigClick) {
                                HTMLInputElement.prototype.click = window._tbOrigClick;
                                window._tbFileHook = false;
                            }
                        }""")
                        async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                            try:
                                await local_btn.click(timeout=3000, force=True)
                            except Exception:
                                await local_btn.evaluate("el => el.click()")
                        fc = await fc_info.value
                        await fc.set_files(str(img_path))
                        file_sent = True
                        logger.debug(f"  {label}: expect_file_chooser 上传成功")
                    except Exception as _e:
                        logger.warning(f"  {label}: expect_file_chooser 也失败: {_e}")
                        await self._force_close_sucai_overlay()
                        return False

            logger.debug(f"  {label}: set_input_files完成（hook路径），等待上传（最多90s）")
        # 上传后不再验证handleId：sucai可能已重新加载（新handleId），接受任何postMessage
        handle_id = None

        # 上传后等待图片出现在库中或触发footer（非realTimeSel模式）
        # 注：图片刚上传时会立刻出现在库缩略图，但CDN处理尚未完成，此时点选无响应。
        # 策略：发现图片后先等4s（CDN完成），若仍无auto-postMessage再手动点选，最多重试3次。
        upload_found_tick = -1    # 图片在库中首次出现时的tick编号
        upload_last_click_tick = -999  # 上次调用_click_sucai_image的tick
        upload_click_count = 0   # 已尝试手动点选次数（最多3次）
        for tick in range(450):  # 90s
            # 检查postMessage（handle_id已为None，接受任何sucai msg）
            received = await self.page.evaluate("() => window.__sucai_received || null")
            if received:
                logger.debug(f"  {label}: 上传postMessage收到，图片已入槽")
                await asyncio.sleep(0.8)
                await self._force_close_sucai_overlay()
                return True
            if not any('sucai-selector' in f.url for f in self.page.frames):
                logger.debug(f"  {label}: 上传后sucai auto-closed，成功")
                return True
            if await self._is_sucai_footer_enabled(sucai_frame):
                logger.debug(f"  {label}: 上传后footer启用，点击确认")
                await self._clear_sucai_msg()
                await self._click_sucai_footer_ok(sucai_frame)
                await asyncio.sleep(0.5)
                if await self._wait_sucai_msg(None, timeout_ms=8000):
                    logger.debug(f"  {label}: 上传footer后收到msg，成功")
                    if any('sucai-selector' in f.url for f in self.page.frames):
                        await self._force_close_sucai_overlay()
                    return True
                logger.debug(f"  {label}: 上传footer点击，视为成功")
                await self._force_close_sucai_overlay()
                return True
            # 检查上传图片是否出现在库中，等CDN完成再点选（最多重试3次）
            if upload_click_count < 3:
                fresh = next((f for f in self.page.frames if 'sucai-selector' in f.url), sucai_frame)
                item = await self._find_sucai_item(fresh, img_path.name)
                if item:
                    sucai_frame = fresh
                    if upload_found_tick < 0:
                        upload_found_tick = tick
                        logger.debug(f"  {label}: 图片已入库，等4s确保CDN完成...")
                    # 首次点选等4s，之后每次重试间隔5s
                    wait_ticks = 20 if upload_click_count == 0 else 25
                    ref_tick = upload_found_tick if upload_click_count == 0 else upload_last_click_tick
                    if tick - ref_tick >= wait_ticks:
                        already = await self.page.evaluate("() => window.__sucai_received || null")
                        if already:
                            logger.debug(f"  {label}: auto-postMessage收到，直接接受")
                            await asyncio.sleep(0.5)
                            await self._force_close_sucai_overlay()
                            return True
                        upload_last_click_tick = tick
                        upload_click_count += 1
                        await self._click_sucai_image(fresh, img_path.name)
                        logger.debug(f"  {label}: _click_sucai_image[{upload_click_count}/3]完成，等postMessage")
                        await asyncio.sleep(1.5)
                        continue
            elif tick - upload_last_click_tick >= 20:
                # 3次点选后4s仍无响应 → 在上传标签页无法选图，提前退出让caller重开sucai走library路径
                logger.debug(f"  {label}: 3次点选均无响应，提前退出等caller重试")
                break
            await asyncio.sleep(0.2)

        logger.warning(f"  {label}: 上传90s无响应，强制关闭")
        await self._force_close_sucai_overlay()
        await asyncio.sleep(0.5)
        return False

    async def _confirm_sucai_dialog(self, frame):
        """在素材选择器 iframe 中自动点击确定/完成按钮（裁剪或确认步骤）"""
        for btn_text in ['确定', '完成', '确认', 'OK']:
            btn = frame.get_by_role('button', name=re.compile(btn_text))
            if await btn.count():
                await btn.first.click()
                await asyncio.sleep(0.5)
                return
        # 也检查父页面（部分确认按钮在父页面）
        for btn_text in ['确定', '完成', '确认']:
            btn = self.page.get_by_role('button', name=re.compile(btn_text))
            if await btn.count():
                visible_btns = [b for b in await btn.all() if await b.is_visible()]
                if visible_btns:
                    await visible_btns[0].click()
                    await asyncio.sleep(0.5)
                    return

    async def _click_set_file(self, locator, img_path: Path) -> bool:
        """点击元素触发文件选择，然后通过 JS 钩子设置文件（主页面版，非 iframe）"""
        # 安装主页面的 file input 拦截钩子
        await self.page.evaluate("""() => {
            if (window._tbPageFileHook) return;
            window._tbPageFileHook = true;
            window._tbPageFilePending = null;
            const orig = HTMLInputElement.prototype.click;
            HTMLInputElement.prototype.click = function() {
                if (this.type === 'file') {
                    if (!this.id) this.id = '_tbpf_' + Date.now();
                    window._tbPageFilePending = this.id;
                    return;
                }
                return orig.call(this);
            };
        }""")
        await self.page.evaluate("() => { window._tbPageFilePending = null; }")

        await locator.click()
        await asyncio.sleep(0.6)

        inp_id = await self.page.evaluate(
            "() => { const id = window._tbPageFilePending; window._tbPageFilePending = null; return id; }"
        )
        if inp_id:
            loc = self.page.locator(f'#{inp_id}')
            if await loc.count():
                await loc.set_input_files(str(img_path))
                await asyncio.sleep(2.5)
                return True

        # 降级：找页面内最后一个 file input
        all_fi = await self.page.locator('input[type="file"]').all()
        if all_fi:
            await all_fi[-1].set_input_files(str(img_path))
            await asyncio.sleep(2.5)
            return True

        return False

    # ── 辅助：按标签文字定位图片上传区域 ─────────────────────────────────

    async def _get_image_section(self, label_text: str):
        """通过标签文字找图片上传区块（与位置和类名无关）"""
        xpath = (
            f'xpath=//span[contains(@class,"info-wrapper-label") and '
            f'normalize-space(.)="{label_text}"]'
            f'/ancestor::*[.//div[contains(@class,"image-list")]][1]'
        )
        loc = self.page.locator(xpath).first
        if await loc.count():
            return loc

        loose = self.page.locator(
            f'[class*="info-wrapper-label"]:has-text("{label_text}")'
        ).first
        if not await loose.count():
            return None

        ancestor_id = await loose.evaluate("""el => {
            let n = el;
            for (let i = 0; i < 12; i++) {
                n = n.parentElement;
                if (!n) return null;
                if (n.querySelector('div.image-empty')) {
                    if (!n.id) n.id = '_tb_img_section_' + Date.now();
                    return n.id;
                }
            }
            return null;
        }""")
        if ancestor_id:
            return self.page.locator(f'#{ancestor_id}').first
        return None

    # ── 辅助：按标签文字定位任意表单区块 ─────────────────────────────────

    async def _get_form_area(self, label_text: str) -> str | None:
        """返回包含 label_text 的 info-wrapper-wrap 的 id，找不到返回 None"""
        return await self.page.evaluate(
            """(name) => {
                const clean = s => s.trim().replace(/[*＊\\s]/g, '');
                const n = clean(name);
                // 方法1：按类名 info-wrapper-label 找
                for (const el of document.querySelectorAll(
                    '[class*="info-wrapper-label"], [class*="sell-component-info-wrapper-label"]'
                )) {
                    const t = clean(el.innerText || el.textContent || '');
                    if (t === n || t.includes(n)) {
                        const wrap = el.closest('[class*="info-wrapper-wrap"], [class*="sell-component-info-wrapper-wrap"]');
                        if (wrap) {
                            if (!wrap.id) wrap.id = '_tb_w_' + Date.now();
                            return wrap.id;
                        }
                    }
                }
                // 方法2：专门处理类目属性区 sell-catProp-item 内的 label.label
                for (const item of document.querySelectorAll('.sell-catProp-item')) {
                    const lbl = item.querySelector('label.label');
                    if (!lbl) continue;
                    const t = clean(lbl.innerText || lbl.textContent || '');
                    if (t === n || t.includes(n)) {
                        if (!item.id) item.id = '_tb_w_' + Date.now();
                        return item.id;
                    }
                }
                // 方法3：不依赖类名，直接按文字找 label/span，再向上找最近的 wrap
                const sellForm = document.querySelector('[class*="sell-form"], [class*="sku"], form') || document.body;
                for (const el of sellForm.querySelectorAll('label, span, div')) {
                    const t = clean(el.innerText || el.textContent || '');
                    if (t === n) {
                        // 向上找包含 input/select/button 的容器
                        let p = el.parentElement;
                        for (let i = 0; i < 6; i++) {
                            if (!p) break;
                            if (p.querySelector('input, select, button[class*="select"]')) {
                                if (!p.id) p.id = '_tb_w_' + Date.now();
                                return p.id;
                            }
                            p = p.parentElement;
                        }
                    }
                }
                return null;
            }""",
            label_text
        )

    # ── Step3: 上传主图 ────────────────────────────────────────────────────

    async def _upload_main_images(self, product: Product):
        if not product.main_images:
            logger.warning(f"[{product.seq}] 无主图，跳过")
            return

        # 检查已填槽位数（上次运行可能已成功上传部分图片）
        section = await self._get_image_section('1:1主图')
        if section is None:
            section = self.page.locator('div.sell-component-simply-images').first
        already_filled = 0
        if await section.count():
            empty = await section.locator('div.image-empty').count()
            total_slots = 5
            already_filled = max(0, total_slots - empty)
            if already_filled:
                logger.debug(f"  1:1主图: 已有 {already_filled} 张在槽位，跳过前 {already_filled} 张")

        images = product.main_images[:5]
        total = len(images)
        logger.debug(f"上传1:1主图 {total} 张（已填 {already_filled} 张）…")

        for i, img_path in enumerate(images):
            if i < already_filled:
                logger.debug(f"  主图 {i+1}: 槽位已有图，跳过 [{img_path.name}]")
                continue
            self._step(f'主图 {i+1}/{total}')
            try:
                ok = await self._upload_via_sucai_iframe(img_path, i)
                if ok:
                    logger.debug(f"  主图 {i+1}/{total} 完成")
                    await asyncio.sleep(2.0)
                    await self.human.pause(0.5, 1.0)
                else:
                    logger.warning(f"  主图 {i+1} 上传失败，继续下一张")
                    await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"  主图 {i+1} 上传异常: {e}")
                await self.page.keyboard.press('Escape')

        await self.human.between_fields()

    # ── Step3b: 上传3:4主图 ─────────────────────────────────────────────────

    async def _upload_main_images_3x4(self, product: Product):
        if not product.main_images_3x4:
            return
        logger.debug(f"上传3:4主图 {len(product.main_images_3x4)} 张…")

        section = await self._get_image_section('3:4主图')
        if section is None:
            section = await self._get_image_section('竖版主图')
        if section is None:
            logger.warning(f"[{product.seq}] 未找到3:4主图上传区，跳过")
            return

        already_filled_3x4 = 0
        empty_3x4 = await section.locator('div.image-empty').count()
        already_filled_3x4 = max(0, 5 - empty_3x4)
        if already_filled_3x4:
            logger.debug(f"  3:4主图: 已有 {already_filled_3x4} 张，跳过前 {already_filled_3x4} 张")

        images_3x4 = product.main_images_3x4[:5]
        total = len(images_3x4)
        for i, img_path in enumerate(images_3x4):
            if i < already_filled_3x4:
                logger.debug(f"  3:4主图 {i+1}: 槽位已有图，跳过 [{img_path.name}]")
                continue
            self._step(f'3:4主图 {i+1}/{total}')
            try:
                if await self.page.locator('.next-overlay-wrapper.opened').count():
                    await self._force_close_sucai_overlay()
                    await asyncio.sleep(0.5)

                slot = section.locator('div.image-empty').first
                if not await slot.count():
                    logger.warning(f"  3:4主图 {i+1}: 无更多空槽位")
                    break

                await slot.scroll_into_view_if_needed()
                await slot.click()
                await asyncio.sleep(2.0)

                sucai_frame = await self._get_sucai_frame()
                if sucai_frame is None:
                    await self._force_close_sucai_overlay()
                    await asyncio.sleep(1.5)
                    slot2 = section.locator('div.image-empty').first
                    if await slot2.count():
                        await slot2.scroll_into_view_if_needed()
                        await slot2.click()
                        await asyncio.sleep(2.0)
                        sucai_frame = await self._get_sucai_frame()

                if sucai_frame is None:
                    logger.warning(f"  3:4主图 {i+1}: 素材选择器 iframe 未出现")
                    continue

                await asyncio.sleep(1.5)
                ok = await self._select_from_sucai(sucai_frame, img_path, f"3:4主图{i+1}")
                if ok:
                    logger.debug(f"  3:4主图 {i+1}/{total} 完成")
                    await asyncio.sleep(2.0)
                    await self.human.pause(0.5, 1.0)
                else:
                    logger.warning(f"  3:4主图 {i+1} 上传失败，继续下一张")
                    await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"  3:4主图 {i+1} 上传异常: {e}")
                await self.page.keyboard.press('Escape')

        await self.human.between_fields()

    # ── Step3c: 上传白底图 ────────────────────────────────────────────────

    async def _upload_white_bg_image(self, product: Product):
        if not product.white_bg_images:
            return
        img_path = product.white_bg_images[0]
        logger.debug(f"上传白底图: {img_path.name}")

        section = await self._get_image_section('白底图')
        if section is None:
            logger.warning(f"[{product.seq}] 未找到白底图上传区，跳过")
            return

        # 找空槽位（与主图相同的 image-empty div，或通用 add 按钮）
        slot = section.locator('div.image-empty').first
        if not await slot.count():
            # 回退：找带"添加"文字的按钮或通用上传按钮
            slot = section.locator('[class*="add"], [class*="upload"], button').first
        if not await slot.count():
            logger.warning(f"[{product.seq}] 白底图区无可用槽位，跳过")
            return

        await slot.scroll_into_view_if_needed()
        await slot.click()
        await asyncio.sleep(2.0)

        sucai_frame = await self._get_sucai_frame()
        if sucai_frame is None:
            await self._force_close_sucai_overlay()
            await asyncio.sleep(1.5)
            slot2 = section.locator('div.image-empty').first
            if await slot2.count():
                await slot2.click()
                await asyncio.sleep(2.0)
                sucai_frame = await self._get_sucai_frame()

        if sucai_frame is None:
            logger.warning(f"[{product.seq}] 白底图素材选择器 iframe 未出现")
            return

        await asyncio.sleep(1.5)
        ok = await self._select_from_sucai(sucai_frame, img_path, "白底图1")
        if ok:
            logger.debug(f"  白底图上传完成")
            await asyncio.sleep(2.0)
        else:
            logger.warning(f"  白底图上传失败")
        await self.human.between_fields()

    # ── Step4a: 上传卖点图（图文详情首位）────────────────────────────────────

    async def _upload_selling_images(self, product: Product):
        """卖点图上传：找表单中独立的「卖点图」槽位区块，点击空槽 → sucai iframe → 选图"""
        if not product.selling_images:
            return
        logger.debug(f"上传卖点图 {len(product.selling_images)} 张…")

        # 按可能的标签名依次查找该区块
        section = None
        for label in ('卖点图', '商品亮点图', '亮点图', '卖点'):
            section = await self._get_image_section(label)
            if section is not None:
                logger.debug(f"  卖点图区块: 已通过标签「{label}」定位")
                break
        if section is None:
            logger.warning(f"[{product.seq}] 未找到卖点图上传区，跳过")
            return

        total = len(product.selling_images)
        for i, img_path in enumerate(product.selling_images):
            self._step(f'卖点图 {i+1}/{total}')
            try:
                if await self.page.locator('.next-overlay-wrapper.opened').count():
                    await self._force_close_sucai_overlay()
                    await asyncio.sleep(0.5)

                slot = section.locator('div.image-empty').first
                if not await slot.count():
                    logger.warning(f"  卖点图 {i+1}: 无更多空槽位")
                    break

                await slot.scroll_into_view_if_needed()
                await slot.click(force=True)
                await asyncio.sleep(2.0)

                sucai_frame = await self._get_sucai_frame()
                if sucai_frame is None:
                    await self._force_close_sucai_overlay()
                    await asyncio.sleep(1.5)
                    slot2 = section.locator('div.image-empty').first
                    if await slot2.count():
                        await slot2.scroll_into_view_if_needed()
                        await slot2.click(force=True)
                        await asyncio.sleep(2.0)
                        sucai_frame = await self._get_sucai_frame()

                if sucai_frame is None:
                    logger.warning(f"  卖点图 {i+1}: 素材选择器 iframe 未出现，跳过")
                    continue

                await asyncio.sleep(1.5)
                ok = await self._select_from_sucai(sucai_frame, img_path, f"卖点图{i+1}")
                if ok:
                    logger.debug(f"  卖点图 {i+1}/{total} 完成")
                    await asyncio.sleep(2.0)
                    await self.human.pause(0.5, 1.0)
                else:
                    logger.warning(f"  卖点图 {i+1} 上传失败，继续下一张")
                    await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"  卖点图 {i+1} 上传异常: {e}")
                await self.page.keyboard.press('Escape')

        await self.human.between_fields()

    # ── Step4b: 上传详情图 ─────────────────────────────────────────────────

    async def _upload_detail_images(self, product: Product):
        """
        宝贝详情模块化编辑器图片上传。
        正确流程：点「添加」(add_title) → 点「图片」(add_item) → 素材选择器 → 选图。
        """
        logger.debug(f"上传详情图 {len(product.detail_images)} 张…")

        for i, img_path in enumerate(product.detail_images):
            try:
                # 每次迭代前清理残留 overlay，防止拦截「添加」按钮点击
                if await self.page.locator('.next-overlay-wrapper.opened').count():
                    logger.debug(f"  详情图 {i+1}: 清理残留overlay")
                    await self._force_close_sucai_overlay()
                    await asyncio.sleep(0.5)

                # Step 1: 找并点击「添加」按钮（打开图片/文字菜单）
                add_btn = self.page.locator('div[class*="add_title"]').first
                if not await add_btn.count() or not await add_btn.is_visible():
                    await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(0.5)
                    if not await add_btn.count():
                        logger.warning(f"  详情图 {i+1}: 「添加」按钮未找到，停止")
                        return

                await add_btn.scroll_into_view_if_needed()
                await add_btn.click()
                await asyncio.sleep(0.4)

                # Step 2: 点击「图片」选项（add_item 类名）
                img_opt = self.page.locator('div[class*="add_item"]').first
                if not await img_opt.count():
                    await self.page.keyboard.press('Escape')
                    logger.warning(f"  详情图 {i+1}: 未找到「图片」选项，跳过")
                    continue

                await img_opt.click()
                await asyncio.sleep(1.5)

                # Step 3: 等待素材选择器 iframe（name='' 但 URL 含 sucai-selector-ng）
                sucai_frame = await self._get_sucai_frame()
                if not sucai_frame:
                    logger.debug(f"  详情图 {i+1}: iframe 未出现，关闭残留 overlay 后重试")
                    await self._force_close_sucai_overlay()
                    await asyncio.sleep(1.0)
                    # 重新点「添加」→「图片」
                    add_btn2 = self.page.locator('div[class*="add_title"]').first
                    if await add_btn2.count() and await add_btn2.is_visible():
                        await add_btn2.scroll_into_view_if_needed()
                        await add_btn2.click()
                        await asyncio.sleep(0.4)
                        img_opt2 = self.page.locator('div[class*="add_item"]').first
                        if await img_opt2.count():
                            await img_opt2.click()
                            await asyncio.sleep(1.5)
                            sucai_frame = await self._get_sucai_frame()
                if not sucai_frame:
                    logger.warning(f"  详情图 {i+1}: 素材选择器 iframe 未出现，跳过")
                    await self.page.keyboard.press('Escape')
                    continue

                # Step 4: 在素材库中选图（图片自动加入编辑器，无需确认）
                ok = await self._select_from_sucai(sucai_frame, img_path, f"详情图{i+1}")
                if ok:
                    logger.debug(f"  详情图 {i+1}: 完成 {img_path.name}")
                    await asyncio.sleep(2.0)  # 等待图片模块加入编辑器
                else:
                    logger.warning(f"  详情图 {i+1}: 选图失败 {img_path.name}")

            except Exception as e:
                logger.warning(f"  详情图 {i+1} 失败: {e}")

    # ── Step5: 填写商品属性 ────────────────────────────────────────────────

    async def _expand_attributes_section(self):
        """点击「其他属性」折叠区的箭头图标展开属性列表"""
        await self.page.evaluate('window.scrollTo(0, 500)')
        await asyncio.sleep(0.5)

        # 已展开则直接返回
        already = await self.page.evaluate(
            "() => document.querySelectorAll('.sell-catProp-item').length > 0"
        )
        if already:
            logger.debug("商品属性已展开")
            return

        # 点击 title-info-container 内的 i.next-icon 箭头展开
        arrow = self.page.locator('.title-info-container i.next-icon').first
        if await arrow.count():
            await arrow.scroll_into_view_if_needed()
            await arrow.click()
            await asyncio.sleep(1.0)
            count = await self.page.evaluate(
                "() => document.querySelectorAll('.sell-catProp-item').length"
            )
            logger.debug(f"商品属性已展开，共 {count} 个属性项")
        else:
            logger.debug("未找到属性展开箭头，属性可能默认全部展示")

    async def _close_any_overlay(self):
        """关闭所有残留的overlay（下拉框/sucai等）"""
        await self.page.keyboard.press('Escape')
        await asyncio.sleep(0.2)
        await self.page.evaluate("""() => {
            document.querySelectorAll('.next-overlay-wrapper.opened').forEach(el => {
                el.style.display = 'none';
                el.classList.remove('opened');
            });
            // 同时隐藏 sell-o-select 自定义 popup（否则多个残留会干扰 isVisible 判断）
            document.querySelectorAll('.sell-o-select-popup-overlay').forEach(el => {
                el.style.display = 'none';
            });
        }""")
        await asyncio.sleep(0.2)

    async def _fill_attributes(self, attributes: dict[str, str]):
        if not attributes:
            return
        logger.debug(f"填写属性: {list(attributes.keys())}")

        # 先展开「其他属性」折叠区
        await self._expand_attributes_section()
        # 关闭所有残留overlay（图片上传后可能遗留）
        await self._close_any_overlay()
        await self._screenshot('attributes_before')

        # 等待属性字段渲染（sell-catProp-item 是每个属性行的容器）
        try:
            await self.page.wait_for_function(
                "() => document.querySelectorAll('.sell-catProp-item').length > 0",
                timeout=10000,
            )
        except Exception:
            logger.warning("属性字段等待超时，尝试继续填写")

        for attr_name, attr_value in attributes.items():
            try:
                await self._fill_attr_by_label(attr_name, attr_value)
                await self.human.pause(0.3, 0.6)
            except Exception as e:
                logger.warning(f"  属性 {attr_name!r} 填写失败: {e}")

    # 同一属性在淘宝表单上可能有多种标签写法
    # 桌布类目(121458013)实际22个属性字段：
    #   表面材质/适用场景/形状/主图案类型/材质/产地/底层材质/定制服务/防滑性能/风格/
    #   工艺类型/功能/固定方式/货号/款式/耐温范围/品牌/清洗方式/上市时间/适用季节/适用桌型/台板厚度
    _ATTR_ALIASES: dict[str, list[str]] = {
        '表面材质':   ['材质', '面料材质', '面料'],   # Excel列名→Taobao表单标签
        '面料材质':   ['材质', '表面材质', '面料'],
        '工艺类型':   ['工艺'],
        '使用桌型':   ['适用桌型', '桌型'],
        '主图案类型': ['图案类型', '图案'],
        '风格':       ['风格标签', '风格描述'],
        '品牌':       ['品牌名称'],
        '适用场景':   ['场景'],
        # '厚度' 故意不在此处：台板厚度不适用于桌布，已从sku_reader映射中移除
    }

    # Excel值→淘宝下拉选项的固定映射（当Excel值不在下拉列表时使用）
    _ATTR_VALUE_REMAP: dict[tuple, str] = {
        ('主图案类型', '碎花'):   '碎花图案',
        ('主图案类型', '波点'):   '几何纹路',
        ('工艺类型', '机器织造/数码印花'): '数码印花',
        ('工艺类型', '涤纶织造/涤纶印花'): '数码印花',
    }

    async def _fill_attr_by_label(self, attr_name: str, attr_value: str):
        """通过标签文字定位属性行，自动识别输入类型；找不到时尝试同义词"""
        # 依次尝试主名称和别名
        candidates = [attr_name] + self._ATTR_ALIASES.get(attr_name, [])
        area_id = None
        used_name = attr_name
        for cand in candidates:
            area_id = await self._get_form_area(cand)
            if area_id:
                used_name = cand
                break
        if not area_id:
            logger.debug(f"  未找到属性标签 {attr_name!r}（含别名 {candidates[1:]}），跳过")
            return
        if used_name != attr_name:
            logger.debug(f"  属性 {attr_name!r} 通过别名 {used_name!r} 找到")

        area = self.page.locator(f'#{area_id}')
        await area.scroll_into_view_if_needed()

        # "请选择"型：点击下拉选项
        sel_input = area.locator('input[placeholder*="请选择"]').first
        if await sel_input.count():
            # 检查是否有固定remap（已知不匹配的情况）
            remapped = self._ATTR_VALUE_REMAP.get((attr_name, attr_value))
            fill_value = remapped if remapped else attr_value
            if remapped:
                logger.debug(f"  {attr_name}: 值 {attr_value!r} remap→{remapped!r}")

            # 先关闭残留overlay，再点此下拉框
            await self._close_any_overlay()
            try:
                await sel_input.click(timeout=5000)
            except Exception:
                await sel_input.click(force=True)
            await asyncio.sleep(0.5)
            # 截图记录下拉选项（用于调试/学习可用选项）
            await self._screenshot(f'dropdown_{attr_name}')
            # 读取所有可用选项供日志参考
            all_options: list[str] = []
            try:
                all_options = await self.page.evaluate("""() => {
                    const isVisible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
                    // 优先取可见的 sell-o-select-popup-overlay
                    let dd = [...document.querySelectorAll('.sell-o-select-popup-overlay')].find(isVisible);
                    if (!dd) dd = document.querySelector(
                        '.next-select-dropdown:not([style*="display: none"]),' +
                        '.next-overlay-wrapper.opened .next-select-menu'
                    );
                    if (!dd) return [];
                    return [...dd.querySelectorAll('li,div.info-content,div[class*="option"]')].map(el => (el.innerText||'').trim()).filter(t=>t);
                }""")
                if all_options:
                    logger.debug(f"  {attr_name} 可用选项(前15): {all_options[:15]}")
            except Exception:
                pass
            try:
                dropdown = self.page.locator('.next-select-dropdown:visible, .next-overlay-wrapper.opened, .sell-o-select-popup-overlay:visible')
                keywords = [kw.strip() for kw in re.split(r'[/，、,]', fill_value) if kw.strip() and len(kw.strip()) >= 2]

                # 预滚动：在搜索前先滚动list找选项（处理选项在fold以下/懒加载情况）
                pre_scroll = await self.page.evaluate("""async (text) => {
                    // 辅助：判断元素是否可见（有实际尺寸）
                    const isVisible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };

                    // 优先找可见的 sell-o-select-popup-overlay（可能有多个残留的隐藏版本）
                    let list = [...document.querySelectorAll('.sell-o-select-popup-overlay .options-content')].find(isVisible);

                    // 若未找到，回退到标准 Fusion Design 容器
                    if (!list) {
                        const SELS = [
                            '.next-select-dropdown:not([style*="display:none"]) ul',
                            '.next-select-dropdown:not([style*="display: none"]) ul',
                            '.next-overlay-wrapper.opened ul',
                            '.next-select-dropdown:not([style*="display:none"]) .next-select-menu',
                            '.next-select-dropdown:not([style*="display: none"]) .next-select-menu',
                            '.next-overlay-wrapper.opened .next-select-menu',
                            '.next-select-dropdown:not([style*="display:none"])',
                            '.next-select-dropdown:not([style*="display: none"])',
                            '.next-overlay-wrapper.opened',
                        ];
                        for (const sel of SELS) { const el = document.querySelector(sel); if (el && isVisible(el)) { list = el; break; } }
                    }
                    if (!list) return null;

                    // 循环滚底直到找到目标或 scrollHeight 不再增长（最多8次）
                    let prevHeight = -1;
                    for (let i = 0; i < 8; i++) {
                        list.scrollTop = list.scrollHeight;
                        await new Promise(r => setTimeout(r, 350));
                        const items = [...list.querySelectorAll('li, [role="option"], div.info-content, div[class*="option"]')];
                        const m = items.find(el => (el.innerText || el.textContent || '').trim().includes(text));
                        if (m) { m.scrollIntoView({block:'center'}); return (m.innerText||'').trim(); }
                        if (list.scrollHeight === prevHeight) break;  // 没有更多内容
                        prevHeight = list.scrollHeight;
                    }
                    return null;
                }""", fill_value)
                if pre_scroll:
                    logger.debug(f"  {attr_name}: 预滚动找到 {pre_scroll!r}")

                # 若dropdown有搜索框，用第一个关键词过滤
                search_inp = dropdown.locator('input[type="text"], input[type="search"]').first
                if await search_inp.count() and keywords and not pre_scroll:
                    # 用focus()+keyboard.type代替click()+_react_fill，避免click事件关闭dropdown
                    try:
                        await search_inp.focus()
                    except Exception:
                        pass
                    await asyncio.sleep(0.15)
                    await self.page.keyboard.press('Control+a')
                    await asyncio.sleep(0.05)
                    await self.page.keyboard.type(keywords[0][:8], delay=60)
                    await asyncio.sleep(1.0)  # 给过滤列表足够渲染时间

                # 精确匹配 → 逐关键词模糊匹配
                option = dropdown.get_by_text(fill_value, exact=True).first
                if not await option.count():
                    for kw in keywords:
                        option = dropdown.get_by_text(kw, exact=True).first
                        if await option.count():
                            break
                        option = dropdown.get_by_text(kw).first
                        if await option.count():
                            break

                await option.wait_for(timeout=2000)
                await option.click()
                logger.debug(f"  {attr_name}: 选择 {fill_value!r}")

                # 多选dropdown（使用桌型/适用场景等逗号分隔值）：继续选剩余关键词
                if len(keywords) > 1:
                    await asyncio.sleep(0.3)
                    for kw in keywords[1:]:
                        if await search_inp.count():
                            await search_inp.fill('')
                            await search_inp.type(kw[:8], delay=60)
                            await asyncio.sleep(0.4)
                        extra = dropdown.get_by_text(kw, exact=True).first
                        if not await extra.count():
                            extra = dropdown.get_by_text(kw).first
                        if await extra.count():
                            await extra.click()
                            logger.debug(f"  {attr_name}: 追加选择 {kw!r}")
                            await asyncio.sleep(0.2)
            except PWTimeout:
                # 精确/关键词匹配失败，尝试：子串片段匹配 → 下拉可用选项最相似匹配
                matched = False
                try:
                    dropdown2 = self.page.locator('.next-select-dropdown:visible, .next-overlay-wrapper.opened, .sell-o-select-popup-overlay:visible')
                    # 子串片段：从fill_value和keywords提取2-4字片段
                    tokens = set()
                    for src in ([fill_value] + keywords):
                        for n in range(min(len(src), 4), 1, -1):
                            for i in range(len(src) - n + 1):
                                tokens.add(src[i:i+n])
                    for tok in sorted(tokens, key=lambda t: -len(t)):
                        opts = dropdown2.get_by_text(tok, exact=False)
                        if await opts.count():
                            await opts.first.click()
                            logger.debug(f"  {attr_name}: 子串片段 {tok!r} 匹配成功")
                            matched = True
                            break
                    # 若仍未匹配，找可用选项中与all_options最相似的（交集字符最多）
                    if not matched and all_options:
                        def overlap(a: str, b: str) -> int:
                            return sum(1 for c in set(a) if c in b)
                        best = max(all_options, key=lambda o: overlap(fill_value, o))
                        if overlap(fill_value, best) >= 1:
                            best_opt = dropdown2.get_by_text(best, exact=True).first
                            if await best_opt.count():
                                await best_opt.click()
                                logger.debug(f"  {attr_name}: 字符重叠最优匹配 {best!r}")
                                matched = True
                    # 终极兜底：清空搜索框 → JS滚动+遍历所有li找含fill_value的选项
                    if not matched:
                        try:
                            # 清空搜索框让所有选项重新显示，再滚动查找
                            if await search_inp.count():
                                await search_inp.focus()
                                await asyncio.sleep(0.05)
                                await self.page.keyboard.press('Control+a')
                                await self.page.keyboard.press('Delete')
                                await asyncio.sleep(0.5)
                            scroll_txt = await self.page.evaluate("""async (text) => {
                                const isVisible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
                                let dd = [...document.querySelectorAll('.sell-o-select-popup-overlay .options-content')].find(isVisible);
                                if (!dd) {
                                    const SELS = [
                                        '.next-select-dropdown:not([style*="display:none"]) ul',
                                        '.next-select-dropdown:not([style*="display: none"]) ul',
                                        '.next-overlay-wrapper.opened ul',
                                        '.next-select-dropdown:not([style*="display:none"]) .next-select-menu',
                                        '.next-select-dropdown:not([style*="display: none"]) .next-select-menu',
                                        '.next-overlay-wrapper.opened .next-select-menu',
                                        '.next-select-dropdown:not([style*="display:none"])',
                                        '.next-select-dropdown:not([style*="display: none"])',
                                        '.next-overlay-wrapper.opened',
                                    ];
                                    for (const sel of SELS) { const el = document.querySelector(sel); if (el && isVisible(el)) { dd = el; break; } }
                                }
                                if (!dd) return null;
                                let prevH = -1;
                                for (let i = 0; i < 8; i++) {
                                    dd.scrollTop = dd.scrollHeight;
                                    await new Promise(r => setTimeout(r, 350));
                                    const items = [...dd.querySelectorAll('li, [role="option"], div.info-content, div[class*="option"]')];
                                    const m = items.find(el => (el.innerText || el.textContent || '').trim().includes(text));
                                    if (m) { m.scrollIntoView({block:'center'}); return (m.innerText||'').trim(); }
                                    if (dd.scrollHeight === prevH) break;
                                    prevH = dd.scrollHeight;
                                }
                                return null;
                            }""", fill_value)
                            if scroll_txt:
                                await asyncio.sleep(0.3)
                                scroll_opt = dropdown2.get_by_text(fill_value, exact=False).first
                                if not await scroll_opt.count():
                                    scroll_opt = dropdown2.get_by_text(scroll_txt[:20], exact=False).first
                                if await scroll_opt.count():
                                    await scroll_opt.click()
                                    logger.debug(f"  {attr_name}: JS滚动找到 {scroll_txt!r}")
                                    matched = True
                        except Exception as ex2:
                            logger.debug(f"  {attr_name}: JS滚动查找异常 {ex2}")
                except Exception as ex:
                    logger.debug(f"  {attr_name}: 降级匹配异常 {ex}")
                if not matched:
                    await self._close_any_overlay()
                    logger.warning(f"  {attr_name}: 选项 {attr_value!r} 未找到任何匹配（已关闭overlay），跳过")
            return

        # "请输入"型：文本输入，可能有建议列表
        txt_input = area.locator('input[placeholder*="请输入"]').first
        if await txt_input.count():
            await txt_input.click()
            await self._react_fill(txt_input, attr_value)
            await asyncio.sleep(0.5)
            try:
                option = self.page.locator(
                    '.next-select-dropdown:visible, .next-overlay-wrapper:visible'
                ).get_by_text(attr_value, exact=True).first
                await option.wait_for(timeout=2000)
                await option.click()
                logger.debug(f"  {attr_name}: 输入并选择 {attr_value!r}")
            except PWTimeout:
                await self.page.keyboard.press('Enter')
                logger.debug(f"  {attr_name}: 直接输入 {attr_value!r}")
            return

        logger.debug(f"  {attr_name}: 未找到可用输入框，跳过")

    # ── Step6: 设置销售规格（通过 SKU 抽屉）─────────────────────────────

    async def _fill_sku_specs(self, product: Product):
        """
        点击「+ 创建规格」打开 sku-decouple-drawer，
        切换到「单层展示·自定义填写规格」，逐个输入规格值后点击「确认创建」。
        """
        logger.debug(f"设置规格: 颜色={product.colors}, 尺寸={product.sizes}")

        if len(product.colors) <= 1 and product.sizes:
            spec_values = product.sizes
            logger.debug("  单色多尺寸，使用尺寸作为规格值")
        elif product.colors:
            spec_values = product.colors
        else:
            logger.warning("无规格值，跳过")
            return

        await self.page.keyboard.press('Escape')
        await asyncio.sleep(0.5)

        # 先滚动到规格区域使按钮可见
        sku_sec = self.page.locator('#sell-field-sku').first
        if await sku_sec.count():
            await sku_sec.scroll_into_view_if_needed()
            await asyncio.sleep(0.4)
        else:
            await self.page.evaluate('window.scrollTo(0, 700)')
            await asyncio.sleep(0.4)

        # 方法1：#sell-field-sku 内第一个 button（无规格时为"创建规格"，有规格时可能是"设置"）
        clicked = await self.page.evaluate("""() => {
            const b = document.querySelector('#sell-field-sku button');
            if (b) { b.click(); return b.innerText.trim() || 'ok'; }
            return null;
        }""")
        logger.debug(f"  规格按钮(方法1): {clicked!r}")
        await asyncio.sleep(2.0)

        # 方法2：若抽屉未出现，Playwright 找「编辑规格/创建规格」按钮
        # 注意：方法1可能点的是"设置"（显示模式切换），方法2专门找抽屉入口
        if not await self.page.locator('.sku-decouple-drawer').count():
            for name_pat in [r'编辑规格', r'创建规格', r'添加规格', r'添加颜色']:
                spec_btn = self.page.get_by_role('button', name=re.compile(name_pat)).first
                if await spec_btn.count():
                    await spec_btn.scroll_into_view_if_needed()
                    await spec_btn.click()
                    clicked = await spec_btn.inner_text()
                    logger.debug(f"  规格按钮(方法2/{name_pat}): {clicked!r}")
                    await asyncio.sleep(2.0)
                    if await self.page.locator('.sku-decouple-drawer').count():
                        break

        # 方法3：在 #sell-field-sku 内找含"编辑/修改/规格"文字的按钮（链接式文字按钮）
        if not await self.page.locator('.sku-decouple-drawer').count():
            edit_res = await self.page.evaluate("""() => {
                const sec = document.querySelector('#sell-field-sku');
                if (!sec) return null;
                // 所有可见按钮（含 a 标签）
                const elems = [...sec.querySelectorAll('button, a')].filter(b => {
                    const r = b.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                });
                // 优先找含「编辑/修改/规格」的
                for (const b of elems) {
                    const t = (b.innerText||b.textContent||'').trim();
                    if (/编辑|修改|规格设置/.test(t) && !/设置$/.test(t)) {
                        b.click(); return '编辑:' + t;
                    }
                }
                // 降级：找第二个可见按钮（第一个通常是"设置"模式切换）
                if (elems.length >= 2) {
                    elems[1].click();
                    return '第2个:' + (elems[1].innerText||'').trim();
                }
                return null;
            }""")
            logger.debug(f"  规格按钮(方法3): {edit_res!r}")
            if edit_res:
                await asyncio.sleep(2.0)

        # 等抽屉出现（最多10秒）
        for _ in range(12):
            if await self.page.locator('.sku-decouple-drawer').count():
                break
            await asyncio.sleep(0.8)
        if not await self.page.locator('.sku-decouple-drawer').count():
            logger.warning("SKU 规格抽屉未出现，跳过")
            return

        # 若已有规格（重试场景），先重置防止重复
        await self._reset_existing_specs_if_any()

        # 用 Playwright locator 点击「单层展示」radio
        await self._switch_drawer_to_single_mode()
        await self._screenshot('sku_drawer_opened')

        # 填写规格值
        ok = await self._fill_drawer_spec_values(spec_values)
        if not ok:
            logger.warning("规格值填写失败")
            await self.page.keyboard.press('Escape')
            await self._dismiss_exit_dialog()
            return

        # 点「确认创建」
        confirm_btn = self.page.locator(
            '.sku-decouple-drawer button.next-btn-primary:not(.next-btn-text)'
        ).filter(has_text=re.compile(r'确认创建|确认|创建')).first
        if not await confirm_btn.count():
            confirm_btn = self.page.locator(
                '.sku-decouple-drawer button.next-btn-primary:not(.next-btn-text)'
            ).first
        if await confirm_btn.count():
            await confirm_btn.click()
            await asyncio.sleep(2.5)
            # 验证抽屉是否成功关闭（若仍可见说明有校验错误）
            if await self.page.locator('.sku-decouple-drawer').is_visible():
                logger.warning("「确认创建」后抽屉仍可见（校验失败），再次点击确认")
                await self._screenshot('sku_confirm_failed')
                await asyncio.sleep(0.5)
                if await confirm_btn.count():
                    await confirm_btn.click()
                    await asyncio.sleep(2.5)
                if await self.page.locator('.sku-decouple-drawer').is_visible():
                    logger.warning("  二次确认仍失败，强制关闭抽屉")
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    await self._dismiss_exit_dialog()
                    await asyncio.sleep(0.5)
                else:
                    logger.debug("  二次确认成功")
            else:
                logger.debug("SKU 规格已提交，抽屉已关闭")
        else:
            logger.warning("未找到「确认创建」按钮")
            await self.page.keyboard.press('Escape')
            await self._dismiss_exit_dialog()

        try:
            # 滚动到 SKU 区域触发渲染，再等表格出现
            await self.page.evaluate("""() => {
                const sec = document.querySelector('#sell-field-sku');
                if (sec) sec.scrollIntoView({block: 'center'});
            }""")
            await asyncio.sleep(1.0)   # 给 React 更多时间渲染

            # 尝试多种 SKU 表格行选择器（淘宝可能使用 tr 或 div 实现）
            found = False
            for selector in [
                'tr.sku-table-row',
                'tr[class*="sku-table-row"]',
                'tr[class*="skuTableRow"]',
                '[class*="sku-table"] tr',
                '[class*="skuTable"] tr',
                '[class*="sku_table"] tr',
            ]:
                if await self.page.locator(selector).count():
                    logger.debug(f"SKU 表格已生成 (selector={selector!r})")
                    found = True
                    break

            if not found:
                # 最后手段：等待任何含输入框的 SKU 相关行出现
                try:
                    await self.page.wait_for_selector(
                        'tr.sku-table-row, tr[class*="sku"], [class*="sku-table"] tr',
                        timeout=15000,
                    )
                    logger.debug("SKU 表格已生成（fallback wait）")
                except PWTimeout:
                    logger.warning("SKU 表格未出现，继续（将以单价/总库存模式填写）")
        except Exception as e:
            logger.warning(f"SKU 表格等待异常: {e}")

    async def _reset_existing_specs_if_any(self):
        """若抽屉中已有规格（重试时残留），逐个点 trash 按钮删除，避免产生重复"""
        await asyncio.sleep(0.5)
        has_specs = await self.page.evaluate("""() => {
            const d = document.querySelector('.sku-decouple-drawer');
            if (!d) return false;
            return /商品规格[^\\d]*(\\d+)/.test(d.innerText || '');
        }""")
        if not has_specs:
            return

        logger.debug("  抽屉已有规格，逐个删除…")
        # 已确认规格的 trash 按钮 class 含 color-delete 但不含 not-show-icon
        # （+ 按钮 class 同时含 color-delete 和 not-show-icon）
        for _ in range(20):
            deleted = await self.page.evaluate("""() => {
                const d = document.querySelector('.sku-decouple-drawer');
                if (!d) return false;
                // 已确认规格 trash 按钮：class 含 color-delete 且不含 not-show-icon
                for (const btn of d.querySelectorAll('button[class*="color-delete"]')) {
                    if (btn.className.includes('not-show-icon')) continue; // 跳过 + 按钮
                    const r = btn.getBoundingClientRect();
                    if (r.width > 0 && !btn.disabled) { btn.click(); return true; }
                }
                return false;
            }""")
            if not deleted:
                break
            await asyncio.sleep(0.4)
        logger.debug("  已有规格已全部删除")

    async def _switch_drawer_to_single_mode(self):
        """点击「单层展示·自定义填写规格」radio，确保模式切换生效"""
        # 方法A: get_by_role 找 radio input（Playwright 正确定位 radio 元素）
        radio = self.page.locator('.sku-decouple-drawer').get_by_role(
            'radio', name=re.compile(r'单层展示')
        ).first
        if await radio.count():
            try:
                await radio.click(force=True, timeout=3000)
                await asyncio.sleep(1.5)
                if await radio.is_checked():
                    logger.debug("  已切换到「单层展示」（方法A）")
                    return
                logger.debug("  方法A click 未生效，尝试方法B")
            except Exception as e:
                logger.debug(f"  方法A 失败: {e}")

        # 方法B: JS 精确找 radio input，触发 click + change 事件
        r = await self.page.evaluate("""() => {
            const d = document.querySelector('.sku-decouple-drawer');
            if (!d) return 'no-drawer';

            // 1. 找所有 radio input，看哪个关联的 label 含「单层展示」
            for (const inp of d.querySelectorAll('input[type="radio"]')) {
                const lbl = inp.closest('label')
                          || (inp.id ? d.querySelector('label[for="' + inp.id + '"]') : null);
                const txt = (lbl?.innerText || inp.parentElement?.innerText || '').trim();
                if (txt.includes('单层展示')) {
                    inp.click();
                    inp.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    return 'radio-input:' + txt.slice(0, 20);
                }
            }

            // 2. 用文字节点查找最小包含元素，再找其中的 radio input
            const walker = document.createTreeWalker(d, NodeFilter.SHOW_TEXT);
            let n;
            while ((n = walker.nextNode())) {
                if ((n.nodeValue || '').trim().startsWith('单层展示')) {
                    const el = n.parentElement;
                    const closestLbl = el.closest('label');
                    const inp2 = closestLbl?.querySelector('input[type="radio"]');
                    if (inp2) {
                        inp2.click();
                        inp2.dispatchEvent(new Event('change', {bubbles: true}));
                        return 'text-radio:' + (closestLbl?.innerText || '').slice(0, 20);
                    }
                    // label 本身点击
                    (closestLbl || el).click();
                    return 'text-label:' + el.tagName;
                }
            }
            return 'not-found';
        }""")
        logger.debug(f"  JS切换模式: {r}")
        await asyncio.sleep(1.5)

        # 验证是否切换成功
        mode_ok = await self.page.evaluate("""() => {
            const d = document.querySelector('.sku-decouple-drawer');
            if (!d) return null;
            for (const inp of d.querySelectorAll('input[type="radio"]')) {
                if (inp.checked) {
                    const lbl = inp.closest('label');
                    return (lbl?.innerText || inp.value || '?').trim().slice(0, 20);
                }
            }
            return 'no-checked-radio';
        }""")
        if mode_ok and '单层' in mode_ok:
            logger.debug(f"  模式切换确认: {mode_ok}")
        elif mode_ok:
            logger.warning(f"  模式切换后当前选中: {mode_ok!r}（预期「单层展示」）")

    async def _fill_drawer_spec_values(self, values: list[str]) -> bool:
        """
        在单层展示抽屉中逐个填写规格值。
        流程：每个值填入当前行的输入框 → 点 + 确认为 chip → 点 button.add 添加新行 → 重复。
        每个规格值独占一行（单层展示下每行=一个 SKU 变体）。
        """
        for i, value in enumerate(values):
            # 始终取最后一个输入框（新添加行的空输入框）
            last_inp = self.page.locator(
                '.sku-decouple-drawer input:not([type="radio"]):not([type="checkbox"])'
            ).last
            if not await last_inp.count():
                logger.warning(f"  规格输入框未找到 ({i+1}/{len(values)})")
                return False

            # 填写值
            await last_inp.click()
            await asyncio.sleep(0.2)
            await last_inp.fill(value)
            await asyncio.sleep(0.5)

            # 点击本行的 + 按钮（通过位置法：找 input 右侧最近的 button，避免误触 chip 的删除×）
            plus_pos = await self.page.evaluate("""() => {
                const d = document.querySelector('.sku-decouple-drawer');
                if (!d) return null;
                const inputs = [...d.querySelectorAll('input:not([type="radio"]):not([type="checkbox"])')];
                const inp = inputs.at(-1);
                if (!inp) return null;
                const ir = inp.getBoundingClientRect();
                // 找在 input 右侧、同行（y 偏差 < 30px）的所有可见按钮
                const btns = [...d.querySelectorAll('button:not([disabled])')].filter(b => {
                    const r = b.getBoundingClientRect();
                    return r.width > 0 && r.height > 0
                        && Math.abs(r.y + r.height/2 - (ir.y + ir.height/2)) < 30
                        && r.x > ir.x + ir.width - 5;  // 在 input 右边
                });
                if (!btns.length) return null;
                btns.sort((a, b) => a.getBoundingClientRect().x - b.getBoundingClientRect().x);
                const r = btns[0].getBoundingClientRect();
                return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
            }""")
            if plus_pos:
                await self.page.mouse.click(plus_pos['x'], plus_pos['y'])
                await asyncio.sleep(0.8)
            else:
                # 备用：按 Enter 键确认（部分组件支持）
                await last_inp.press('Enter')
                await asyncio.sleep(0.8)
            logger.debug(f"  规格值 {i+1}/{len(values)}: {value!r} 已确认")

            # 若还有更多值，等待 button.add 启用后点击以添加新行（重试最多4秒）
            if i < len(values) - 1:
                add_pos = None
                for _ in range(20):  # 等待最多 4s
                    add_pos = await self.page.evaluate("""() => {
                        const d = document.querySelector('.sku-decouple-drawer');
                        const btn = d?.querySelector('button.add:not([disabled])');
                        if (!btn) return null;
                        const r = btn.getBoundingClientRect();
                        return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
                    }""")
                    if add_pos:
                        break
                    await asyncio.sleep(0.2)
                if add_pos:
                    await self.page.mouse.click(add_pos['x'], add_pos['y'])
                    await asyncio.sleep(0.6)
                    logger.debug(f"  添加新规格行")
                else:
                    logger.warning(f"  button.add 4s内未启用，继续（规格可能在同一行）")

        return True

    async def _dismiss_exit_dialog(self):
        """处理退出抽屉时的二次确认弹窗（「操作未提交，确定要退出吗？」）"""
        await asyncio.sleep(0.6)
        try:
            ok = self.page.locator('.next-dialog:visible button').filter(
                has_text=re.compile(r'确定|放弃|离开')
            ).first
            if await ok.count():
                await ok.click()
                await asyncio.sleep(0.5)
                logger.debug("  已处理退出确认弹窗")
        except Exception:
            pass

    async def _force_close_all_overlays(self, force_remove: bool = False):
        """关闭页面上所有打开的抽屉/弹窗/overlay，处理「确认退出」确认框"""
        for _ in range(6):
            acted = await self.page.evaluate("""() => {
                // 找「确认退出」类弹窗中的确认按钮
                for (const btn of document.querySelectorAll(
                    '.next-dialog button, [role="dialog"] button'
                )) {
                    const t = (btn.innerText||'').trim();
                    if (/确定|放弃|离开|关闭/.test(t) && !btn.disabled) {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 0) { btn.click(); return '对话框:' + t; }
                    }
                }
                // 找 SKU 抽屉的「取消」按钮
                const drawer = document.querySelector('.sku-decouple-drawer');
                if (drawer) {
                    for (const btn of drawer.querySelectorAll('button')) {
                        const t = (btn.innerText||'').trim();
                        if (/取消/.test(t) && !btn.disabled) {
                            const r = btn.getBoundingClientRect();
                            if (r.width > 0) { btn.click(); return '抽屉取消:' + t; }
                        }
                    }
                }
                return null;
            }""")
            if acted:
                logger.debug(f"  强制关闭: {acted}")
                await asyncio.sleep(0.5)
            else:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.4)
            # 检查 overlay 是否已消失
            backdrop_count = await self.page.locator('.next-overlay-backdrop').count()
            if backdrop_count == 0:
                break
        if force_remove:
            # 最后手段：JS 清除 backdrop；但 .sku-decouple-drawer 只隐藏不移除
            # （移除 drawer DOM 节点会破坏 React fiber 引用，导致后续无法重新打开抽屉）
            removed = await self.page.evaluate("""() => {
                let count = 0;
                // 移除 backdrop
                document.querySelectorAll('.next-overlay-backdrop').forEach(el => {
                    el.remove(); count++;
                });
                // 移除不含规格抽屉的 overlay-wrapper
                const drawer = document.querySelector('.sku-decouple-drawer');
                document.querySelectorAll('.next-overlay-wrapper').forEach(el => {
                    if (!el.contains(drawer)) { el.remove(); count++; }
                });
                // 规格抽屉及其父 wrapper：只隐藏，保留 DOM（React 需要引用）
                if (drawer) {
                    let p = drawer.parentElement;
                    while (p && p !== document.body) {
                        if (p.classList.contains('next-overlay-wrapper') ||
                            p.classList.contains('next-overlay-backdrop')) {
                            p.style.display = 'none';
                            count++;
                            break;
                        }
                        p = p.parentElement;
                    }
                    drawer.style.display = 'none';
                }
                return count;
            }""")
            if removed:
                logger.warning(f"  JS 清除 {removed} 个 overlay 元素（drawer 仅隐藏）")
            await asyncio.sleep(0.3)

    async def _remove_duplicate_specs(self):
        """检查并删除抽屉中重复的规格值（点击重复行右侧的删除按钮）"""
        removed = await self.page.evaluate("""() => {
            const d = document.querySelector('.sku-decouple-drawer');
            if (!d) return 0;
            // 收集所有规格输入框的值
            const inputs = [...d.querySelectorAll('input:not([type="radio"]):not([type="checkbox"])')];
            const seen = new Set();
            let count = 0;
            for (const inp of inputs) {
                const val = inp.value.trim();
                if (!val) continue;
                if (seen.has(val)) {
                    // 找该输入框所在行的删除/color-delete 按钮
                    let p = inp.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (!p) break;
                        const btn = p.querySelector('button[class*="color-delete"], button[class*="delete"]');
                        if (btn && !btn.disabled) {
                            btn.click();
                            count++;
                            break;
                        }
                        p = p.parentElement;
                    }
                } else {
                    seen.add(val);
                }
            }
            return count;
        }""")
        if removed:
            logger.debug(f"  删除了 {removed} 个重复规格")
            await asyncio.sleep(0.8)

    # ── Step7: 设置运费模板和发货时间 ─────────────────────────────────────

    async def _fill_shipping(self, tpl_name: str, delivery_days: int):
        logger.debug(f"设置运费模板: {tpl_name!r}, 发货: {delivery_days}")

        # 滚动到运费区域
        await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.6)')
        await asyncio.sleep(0.5)

        # 通过标签文字定位运费模板行（尝试多种可能的标签名）
        tpl_area_id = None
        for label_try in ('运费模板', '模板', '物流模板', '运费'):
            tpl_area_id = await self._get_form_area(label_try)
            if tpl_area_id:
                logger.debug(f"  运费区域标签匹配: {label_try!r}")
                break

        if tpl_area_id:
            area = self.page.locator(f'#{tpl_area_id}')
            await area.scroll_into_view_if_needed()

            # 检查当前选中值
            try:
                current_val = await area.locator('[class*="next-select"]').inner_text()
            except Exception:
                current_val = ''

            if tpl_name not in current_val:
                trigger = area.locator(
                    '[class*="next-select-trigger"], [class*="next-select"]'
                ).first
                await trigger.click()
                await asyncio.sleep(0.5)
                try:
                    option = self.page.locator(
                        '.next-overlay-wrapper:visible, .next-select-dropdown:visible'
                    ).get_by_text(tpl_name, exact=False).first
                    await option.wait_for(timeout=4000)
                    await option.click()
                    logger.debug(f"  运费模板已选: {tpl_name!r}")
                except PWTimeout:
                    await self.page.keyboard.press('Escape')
                    logger.warning(f"  运费模板 {tpl_name!r} 未在下拉中找到，保留默认")
            else:
                logger.debug(f"  运费模板已是 {tpl_name!r}，无需更改")
        else:
            # 降级：直接找物流服务区域内的 next-select 组件
            logger.warning("未找到运费模板标签，尝试直接定位物流select")
            await self._fill_shipping_by_direct_select(tpl_name)

        # 发货时间 radio（在基础信息区，顶部偏上位置）
        delivery_labels = {0: '今日发', 1: '24小时', 2: '48小时', 3: '大于48'}
        label = delivery_labels.get(delivery_days, '48小时')
        try:
            radio = self.page.get_by_role('radio', name=re.compile(label))
            if await radio.count():
                await radio.first.check()
                logger.debug(f"  发货时间: {label}")
            else:
                logger.warning(f"  发货时间 radio {label!r} 未找到")
        except Exception as e:
            logger.warning(f"  发货时间设置失败: {e}")

        await self.human.between_fields()

    async def _fill_shipping_by_direct_select(self, tpl_name: str):
        """降级：通过「运费模板」标签旁的 next-select 用 Playwright locator 定位点击"""
        # 策略1：找到包含'运费模板'文字的元素，导航到其祖先row，再找select trigger
        label_el = self.page.locator('div, label, span').filter(
            has_text=re.compile(r'^运费模板$')
        ).first
        if await label_el.count():
            await label_el.scroll_into_view_if_needed()
            # 向上找包含 next-select 的父容器（最多 6 层）
            trigger = None
            for xpath_up in ['..', '../..', '../../..', '../../../..', '../../../../..', '../../../../../..']:
                parent = label_el.locator(xpath_up)
                if not await parent.count():
                    continue
                sel = parent.locator('[class*="next-select-trigger"]').first
                if await sel.count() and await sel.is_visible():
                    trigger = sel
                    break
            if trigger:
                await trigger.scroll_into_view_if_needed()
                await trigger.click()
                await asyncio.sleep(0.8)
                try:
                    opt = self.page.locator(
                        '.next-overlay-wrapper.opened, .next-select-dropdown:not([style*="display: none"])'
                    ).get_by_text(tpl_name, exact=False).first
                    await opt.wait_for(timeout=6000)
                    await opt.click()
                    logger.debug(f"  运费模板已选: {tpl_name!r}")
                    return
                except PWTimeout:
                    await self.page.keyboard.press('Escape')
                    logger.warning(f"  下拉中未找到 {tpl_name!r}，保留默认")
                    return

        # 策略2：遍历所有 next-select-trigger，找当前值为"请选择/模板"的
        selects = await self.page.locator('[class*="next-select-trigger"]').all()
        for sel in selects:
            try:
                if not await sel.is_visible():
                    continue
                txt = (await sel.inner_text()).strip()
                if '请选择' in txt or '模板' in txt or not txt:
                    await sel.scroll_into_view_if_needed()
                    await sel.click()
                    await asyncio.sleep(0.8)
                    opt = self.page.locator(
                        '.next-overlay-wrapper.opened, .next-select-dropdown:not([style*="display: none"])'
                    ).get_by_text(tpl_name, exact=False).first
                    await opt.wait_for(timeout=4000)
                    await opt.click()
                    logger.debug(f"  降级选择运费模板: {tpl_name!r}")
                    return
            except Exception:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.2)
                continue
        logger.warning("  运费模板选择未成功，跳过")

    # ── Step8: 启用多件优惠 ────────────────────────────────────────────────

    async def _enable_multi_discount(self, enabled: bool, rate: str):
        if not enabled:
            return
        logger.debug("启用多件优惠…")

        # 先滚动到多件优惠区域使其可见（未滚到时 checkbox 可能报告为 disabled）
        scrolled = await self.page.evaluate("""() => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let n;
            while ((n = walker.nextNode())) {
                if (n.nodeValue && n.nodeValue.trim() === '多件优惠') {
                    const el = n.parentElement;
                    el.scrollIntoView({block: 'center'});
                    return {y: el.getBoundingClientRect().y};
                }
            }
            return null;
        }""")
        if scrolled:
            logger.debug(f"  多件优惠区域滚动到 y={scrolled.get('y')}")
            await asyncio.sleep(0.5)

        # 在「多件优惠」区域容器内找「启用」checkbox（而非全局搜索，避免找到其他区域的「启用」）
        cb_info = await self.page.evaluate("""() => {
            // 1. 找所有「多件优惠」文字节点
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            const discountLabels = [];
            let n;
            while ((n = walker.nextNode())) {
                if (n.nodeValue && n.nodeValue.trim() === '多件优惠') {
                    discountLabels.push(n.parentElement);
                }
            }

            // 2. 对每个「多件优惠」标签，向上走找同时包含「启用」checkbox 的容器
            for (const labelEl of discountLabels) {
                let container = labelEl.parentElement;
                for (let i = 0; i < 12; i++) {
                    if (!container || container === document.body) break;

                    // 找容器内 class=next-checkbox-label 且文字为「启用」的 span
                    const enableSpans = [...container.querySelectorAll('span.next-checkbox-label')].filter(
                        s => s.textContent.trim() === '启用'
                    );
                    if (enableSpans.length > 0) {
                        const s = enableSpans[0];
                        const wrapper = s.closest('.next-checkbox');
                        const cb = wrapper?.querySelector('input[type="checkbox"]')
                                 || s.closest('label')?.querySelector('input[type="checkbox"]');
                        if (!cb) { container = container.parentElement; continue; }

                        // 滚动 checkbox 到视口中央
                        cb.scrollIntoView({block: 'center'});
                        const r = cb.getBoundingClientRect();
                        return {
                            x: Math.round(r.x + r.width / 2),
                            y: Math.round(r.y + r.height / 2),
                            disabled: cb.disabled,
                            checked: cb.checked,
                            containerCls: container.className.slice(0, 60)
                        };
                    }
                    container = container.parentElement;
                }
            }
            return null;
        }""")

        if cb_info:
            logger.debug(f"  「启用」checkbox: disabled={cb_info['disabled']} checked={cb_info['checked']} pos=({cb_info['x']},{cb_info['y']})")
            if cb_info['disabled']:
                logger.warning("  「启用」checkbox 已禁用，跳过")
                return
            if not cb_info['checked']:
                # 用 Playwright 鼠标点击（触发完整事件链）
                await self.page.mouse.click(cb_info['x'], cb_info['y'])
                await asyncio.sleep(0.8)
                logger.debug("  多件优惠「启用」已勾选")
        else:
            # 降级：找 area 内的 checkbox
            area_id = await self._get_form_area('多件优惠')
            if not area_id:
                logger.warning("  未找到多件优惠区域，跳过")
                return
            area = self.page.locator(f'#{area_id}')
            # 遍历找第一个 enabled checkbox
            for cb in await area.get_by_role('checkbox').all():
                disabled = await cb.get_attribute('disabled')
                if disabled is None:
                    if not await cb.is_checked():
                        await cb.click()
                        await asyncio.sleep(0.5)
                        logger.debug("  多件优惠已启用（降级路径）")
                    break
            else:
                logger.warning("  多件优惠所有 checkbox 均已禁用，跳过")
                return

        # 折扣率：若已有默认值则不覆盖（避免 React 状态问题）
        if rate:
            rate_inp = self.page.locator(
                'input[class*="discount"][type="text"], '
                'input[placeholder*="折"]'
            ).first
            if await rate_inp.count():
                existing = await rate_inp.input_value()
                if not existing or existing == '0':
                    await self._react_fill(rate_inp, rate)
                    logger.debug(f"  折扣率已填: {rate}")
                else:
                    logger.debug(f"  折扣率已有默认值 {existing!r}，保留")

        await self.human.between_fields()

    # ── Step9: 填写 SKU 价格和库存（最后执行！）──────────────────────────

    async def _fill_sku_prices(self, product: Product):
        """
        填写价格和库存，必须在所有其他字段操作完成后调用，
        否则 React 重渲染会清空这些值。
        """
        logger.debug("填写SKU价格和库存（最后步骤）…")
        await asyncio.sleep(1.5)   # 等待 SKU 表格渲染稳定

        await self.page.evaluate("""() => {
            const sec = document.querySelector('#sell-field-sku');
            if (sec) sec.scrollIntoView({block: 'center'});
        }""")
        await asyncio.sleep(0.5)
        await self._screenshot('sku_before_price')

        # 多种 SKU 表格行选择器（兼容 tr 和 div 实现）
        rows = []
        for selector in [
            'tr.sku-table-row',
            'tr[class*="sku-table-row"]',
            'tr[class*="skuTableRow"]',
            '[class*="sku-table"] tr',
            '[class*="skuTable"] tr',
            '[class*="sku-decouple"] tr',
        ]:
            rows = await self.page.locator(selector).all()
            if rows:
                break
        logger.debug(f"  SKU 表格行: {len(rows)} 行")

        if rows:
            await self._fill_sku_table(product, rows)
        else:
            # 新版面板：用JS按规格值文字定位各行的价格/库存输入框
            filled = await self._fill_sku_by_size_js(product)
            if not filled:
                logger.warning("SKU 表格行未找到，尝试填写一级价/总库存")
                await self._fill_single_price_stock(product)

        await self.human.between_fields()

    async def _fill_sku_by_size_js(self, product: Product) -> bool:
        """新版SKU面板：按规格值文字定位各行的价格/库存输入框并填写"""
        sizes = [sku.size for sku in product.skus]
        row_inputs = await self.page.evaluate("""(sizes) => {
            const results = [];
            for (const size of sizes) {
                // 找包含该规格值的叶子文本节点所在行
                let rowEl = null;
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let n;
                while ((n = walker.nextNode())) {
                    if (n.nodeValue && n.nodeValue.trim() === size) {
                        // 向上找含有输入框的行容器（最多找8层）
                        let p = n.parentElement;
                        for (let i = 0; i < 8; i++) {
                            if (!p) break;
                            const inputs = [...p.querySelectorAll(
                                'input[type="text"]:not([disabled]):not([readonly]),' +
                                'input[type="number"]:not([disabled]):not([readonly]),' +
                                'input:not([type]):not([disabled]):not([readonly])'
                            )].filter(inp => {
                                const ph = inp.placeholder || '';
                                return !ph.includes('请选择') && inp.getBoundingClientRect().width > 0;
                            });
                            if (inputs.length >= 2) { rowEl = p; break; }
                            p = p.parentElement;
                        }
                        if (rowEl) break;
                    }
                }
                if (rowEl) {
                    const inputs = [...rowEl.querySelectorAll(
                        'input[type="text"]:not([disabled]):not([readonly]),' +
                        'input[type="number"]:not([disabled]):not([readonly]),' +
                        'input:not([type]):not([disabled]):not([readonly])'
                    )].filter(inp => {
                        const ph = inp.placeholder || '';
                        return !ph.includes('请选择') && inp.getBoundingClientRect().width > 0;
                    });
                    results.push({
                        size,
                        priceId: inputs[0]?.id || null,
                        stockId: inputs[1]?.id || null,
                        count: inputs.length,
                    });
                } else {
                    results.push({size, priceId: null, stockId: null, count: 0});
                }
            }
            return results;
        }""", sizes)

        logger.debug(f"  JS按尺寸定位: {row_inputs}")
        if not any(r.get('priceId') for r in row_inputs):
            return False

        for i, (sku, info) in enumerate(zip(product.skus, row_inputs)):
            price_id = info.get('priceId')
            stock_id = info.get('stockId')
            if price_id:
                inp = self.page.locator(f'input#{price_id}')
                if await inp.count():
                    await inp.scroll_into_view_if_needed()
                    await self._react_fill(inp, str(sku.price))
                    logger.debug(f"  SKU{i+1} {sku.size}: 价格={sku.price}")
                    await asyncio.sleep(0.15)
            if stock_id:
                sinp = self.page.locator(f'input#{stock_id}')
                if await sinp.count():
                    await self._react_fill(sinp, str(sku.stock))
                    logger.debug(f"  SKU{i+1} {sku.size}: 库存={sku.stock}")
                    await asyncio.sleep(0.1)
        return True

    async def _fill_sku_table(self, product: Product, rows):
        """
        按行索引顺序填写价格和库存。
        行文本不包含规格值文字（React 渲染方式），改为按顺序匹配 SKU。
        价格/库存输入框识别：ph='' 的 text 输入，前两个分别是 价格 和 库存。
        """
        skus = product.skus
        for idx, row in enumerate(rows):
            if idx >= len(skus):
                break
            sku = skus[idx]

            # 先滚动行到视口内，再用 Playwright locator 找价格/库存输入框
            await row.scroll_into_view_if_needed()
            await asyncio.sleep(0.1)

            # 找所有可编辑的 text/number 输入，排除「请选择」等下拉触发器
            all_inputs = await row.locator(
                'input[type="text"]:not([disabled]):not([readonly]),'
                'input[type="number"]:not([disabled]):not([readonly]),'
                'input:not([type]):not([disabled]):not([readonly])'
            ).all()
            valid_inputs = []
            for inp in all_inputs:
                ph = (await inp.get_attribute('placeholder') or '').strip()
                if '请选择' not in ph:
                    valid_inputs.append(inp)

            price_inp = valid_inputs[0] if len(valid_inputs) >= 1 else None
            stock_inp = valid_inputs[1] if len(valid_inputs) >= 2 else None

            try:
                if price_inp:
                    await self._react_fill(price_inp, str(sku.price))
                    await asyncio.sleep(0.2)
                if stock_inp:
                    await self._react_fill(stock_inp, str(sku.stock))
                    await asyncio.sleep(0.15)
                logger.debug(
                    f"  行{idx+1} {sku.color}/{sku.size}: "
                    f"{sku.price}元 {sku.stock}件"
                    f"  inputs={len(valid_inputs)}"
                )
            except Exception as e:
                logger.warning(f"  价格/库存填写失败 行{idx+1}: {e}")

    async def _fill_single_price_stock(self, product: Product):
        """无 SKU 规格时填写一级价和总库存"""
        default_sku = product.skus[0] if product.skus else None
        if not default_sku:
            return

        # 一口价支持多种标签名
        for label_kw, alts, value in [
            ('一口价', ['一口价', '一级价', '价格'], str(default_sku.price)),
            ('总库存', ['总库存', '库存'],            str(default_sku.stock)),
        ]:
            area_id = None
            for alt in alts:
                area_id = await self._get_form_area(alt)
                if area_id:
                    logger.debug(f"  {label_kw} 找到标签: {alt!r}")
                    break
            if area_id:
                area = self.page.locator(f'#{area_id}')
                inp = area.locator('input[type="text"], input[type="number"], input').first
                if await inp.count():
                    await self._react_fill(inp, value)
                    logger.debug(f"  {label_kw}: {value}")
                else:
                    logger.warning(f"  {label_kw}: 输入框未找到")
            else:
                logger.warning(f"  未找到 {label_kw} 区域（尝试了 {alts}）")

    # ── Step10: 提交 ──────────────────────────────────────────────────────

    async def _submit(self) -> str:
        if self.dry_run:
            logger.info("【dry_run】表单已填写完成，等待用户手动确认后发布。不自动点击发布按钮。")
            return 'dry_run'
        logger.debug("提交商品信息…")

        await self._screenshot('before_submit')

        btn = self.page.get_by_role('button', name=re.compile(r'提交宝贝信息|发布宝贝|发布商品'))
        if not await btn.count():
            btn = self.page.locator(
                'button.next-btn-primary:not(.next-btn-text)'
            ).filter(has_text=re.compile(r'提交|发布'))
        if not await btn.count():
            logger.error("提交按钮未找到")
            await self._screenshot('submit_not_found')
            return ''

        await btn.first.click()
        logger.debug("  提交按钮已点击，等待页面跳转或成功信号（最多30秒）…")

        # 轮询等待最多 30 秒，检测成功
        for i in range(60):
            await asyncio.sleep(0.5)
            url = self.page.url

            # 1. URL 里有商品 ID
            m = re.search(r'primaryId=(\d{10,})', url)
            if m:
                logger.debug(f"  成功: primaryId={m.group(1)}")
                return m.group(1)
            m = re.search(r'[?&]id=(\d{10,})', url)
            if m:
                logger.debug(f"  成功: id={m.group(1)}")
                return m.group(1)
            m = re.search(r'/(\d{12,})(?:[/?]|$)', url)
            if m:
                logger.debug(f"  成功: path id={m.group(1)}")
                return m.group(1)

            # 2. 页面已离开发布页（说明跳转成功）
            if 'upload.taobao.com' not in url and 'publish' not in url and url not in ('', 'about:blank'):
                try:
                    text = await self.page.inner_text('body')
                    m2 = re.search(r'商品[ID号]*[：:]\s*(\d{10,})', text)
                    if m2:
                        return m2.group(1)
                    m2 = re.search(r'(\d{12,})', url)
                    if m2:
                        return m2.group(1)
                    if any(kw in text for kw in ('发布成功', '上架成功', '提交成功', '已发布', 'success')):
                        logger.debug(f"  发布成功（文本信号）: {url[:80]}")
                        return 'published'
                    logger.debug(f"  页面已跳转到: {url[:80]}")
                    return 'published'
                except Exception:
                    return 'published'

            # 3. 检查页面文字成功信号（还在发布页时）
            try:
                text = await self.page.inner_text('body')
                m2 = re.search(r'商品[ID号]*[：:]\s*(\d{10,})', text)
                if m2:
                    return m2.group(1)
                if any(kw in text for kw in ('发布成功', '上架成功', '提交成功')):
                    logger.debug("  发布成功（页面文字）")
                    return 'published'
            except Exception:
                pass

            # 4. 提交后页面跳到图文描述tab（表单校验错误）— 快速检测，不等满30秒
            if i >= 4:   # 提交后2秒开始检查
                try:
                    errs = await self.page.evaluate("""() => {
                        // 查找红色错误提示文字（排除填写助手建议）
                        const msgs = [];
                        // 左侧 优化建议 面板中「错误」tab 下的条目
                        for (const el of document.querySelectorAll(
                            '[class*="errorItem"], [class*="error-item"], '
                            '.next-form-item-feedback.has-error'
                        )) {
                            const t = (el.innerText || '').trim();
                            if (t && t.length < 100 && !t.startsWith('1、') && !t.startsWith('2、'))
                                msgs.push(t);
                        }
                        // 也找页面内直接显示的红色错误文字（如「1:1主图不能为空」）
                        for (const el of document.querySelectorAll(
                            '[class*="error"][style*="color"], [color="red"], '
                            'span[class*="errorTip"], div[class*="errorMsg"]'
                        )) {
                            const t = (el.innerText || '').trim();
                            if (t && t.length < 80) msgs.push(t);
                        }
                        // 直接找 不能为空 / 必填项未填 类错误文字
                        for (const el of document.querySelectorAll('*')) {
                            const t = (el.childNodes.length === 1 && el.firstChild.nodeType === 3)
                                      ? (el.innerText || '').trim() : '';
                            if (/不能为空|必填项未填/.test(t) && t.length < 60)
                                msgs.push(t);
                        }
                        return [...new Set(msgs)].slice(0, 8);
                    }""")
                    if errs:
                        logger.warning(f"  表单校验错误（提前检测）: {errs}")
                        await self._screenshot('submit_validation_error')
                        return ''
                except Exception:
                    pass

            if i % 6 == 5:
                logger.debug(f"  等待中 ({(i+1)//2}s)… url={url[:60]}")

        # 超时后截图并尝试收集真正的表单校验错误（排除干扰元素）
        await self._screenshot('submit_timeout')
        try:
            err_els = await self.page.locator(
                '.next-form-item-feedback.has-error, '
                '[class*="formItem"][class*="error"] .next-form-item-feedback, '
                'div[class*="error-tip"], span[class*="error-msg"]'
            ).all()
            errs = []
            for el in err_els[:8]:
                try:
                    t = (await el.inner_text()).strip()
                    if t and len(t) < 200:
                        errs.append(t)
                except Exception:
                    pass
            if errs:
                logger.warning(f"  表单校验错误: {errs}")
            else:
                logger.warning("  30秒内未检测到成功跳转，商品可能已发布（请手动确认）")
        except Exception:
            pass
        return ''

    # ── React 兼容输入 ─────────────────────────────────────────────────────

    async def _fill_by_coord(self, pos: dict, value: str):
        """通过坐标点击输入框并使用 press_sequentially 填值（触发完整 React 键盘事件链）"""
        await self.page.mouse.click(pos['x'], pos['y'])
        await asyncio.sleep(0.1)
        # 全选并清空现有内容
        await self.page.keyboard.press('Control+a')
        await asyncio.sleep(0.05)
        await self.page.keyboard.press('Delete')
        await asyncio.sleep(0.05)
        # 逐字符输入，触发 keydown/keypress/input/keyup（React 全部监听）
        await self.page.keyboard.type(value, delay=30)
        await asyncio.sleep(0.1)
        # Tab 触发 blur → onBlur/onChange
        await self.page.keyboard.press('Tab')
        await asyncio.sleep(0.1)

    async def _react_fill(self, locator, value: str):
        """
        填写 React 受控输入框。
        优先 press_sequentially（逐字符键盘事件 → React onChange），
        兜底用 execCommand insertText，最终用 nativeInputValueSetter。
        不在内部按 Tab，避免触发 React 重渲染覆盖已填值。
        """
        await locator.scroll_into_view_if_needed()
        await locator.click()
        await asyncio.sleep(0.1)

        # 方法1: press_sequentially（每字符触发 keydown/keypress/input/keyup → React onChange）
        await self.page.keyboard.press('Control+a')
        await asyncio.sleep(0.05)
        await self.page.keyboard.type(value)   # page.keyboard.type 逐字符输入
        await asyncio.sleep(0.1)

        # 验证是否写入成功
        actual = await locator.input_value()
        logger.debug(f"    react_fill({value!r}): type → {actual!r}")
        if actual == value:
            return

        # 方法2: execCommand insertText
        await locator.click()
        await asyncio.sleep(0.05)
        result = await self.page.evaluate("""(val) => {
            const el = document.activeElement;
            if (!el || !('value' in el)) return 'no-input';
            el.select?.();
            document.execCommand('selectAll');
            document.execCommand('insertText', false, val);
            return el.value;
        }""", value)
        logger.debug(f"    react_fill({value!r}): execCmd → {result!r}")
        actual = await locator.input_value()
        if actual == value:
            return

        # 方法3: nativeInputValueSetter + input/change event
        await self.page.evaluate("""(val) => {
            const el = document.activeElement;
            if (!el) return;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", value)
        actual = await locator.input_value()
        logger.debug(f"    react_fill({value!r}): nativeSetter → {actual!r}")

    # ── 工具方法 ───────────────────────────────────────────────────────────

    async def _ok(self) -> bool:
        return await self.engine.check_popups()

    async def _switch_to_newest_page(self):
        await self.page.wait_for_timeout(600)
        pages = self.engine._context.pages
        if len(pages) > 1:
            new = pages[-1]
            if new != self.page:
                self.engine.page = self.page = new
                self.human.page  = new
                self.engine.popup.page = new
                logger.debug(f"切换标签页: {new.url[:60]}")
                await new.wait_for_load_state('domcontentloaded')

    async def _screenshot(self, name: str):
        p = Path('screenshots') / f'{name}_{int(time.time())}.png'
        p.parent.mkdir(exist_ok=True)
        try:
            await self.page.screenshot(path=str(p))
            logger.info(f"截图已保存: {p}")
        except Exception:
            pass
