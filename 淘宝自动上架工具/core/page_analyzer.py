"""
智能页面元素识别。
优先级：语义定位（文字/角色/占位符）→ DOM启发式扫描 → CSS选择器兜底
不依赖任何固定 CSS 类名，页面改版不影响。
"""
import asyncio
from loguru import logger
from playwright.async_api import Page, Locator, TimeoutError as PWTimeout


class PageAnalyzer:
    def __init__(self, page: Page):
        self.page = page

    # ── 通用查找 ───────────────────────────────────────────────────────────

    async def find_button(self, *labels: str, timeout: int = 5000) -> Locator | None:
        """按文字找按钮/可点击元素"""
        for label in labels:
            for method in [
                lambda l: self.page.get_by_role('button', name=l, exact=True),
                lambda l: self.page.get_by_role('button', name=l),
                lambda l: self.page.get_by_text(l, exact=True),
                lambda l: self.page.locator(f'[class*="btn"]:has-text("{l}")'),
                lambda l: self.page.locator(f'a:has-text("{l}")'),
                lambda l: self.page.locator(f'span:has-text("{l}")').locator('..'),
            ]:
                try:
                    loc = method(label)
                    await loc.first.wait_for(state='visible', timeout=timeout)
                    logger.debug(f'找到按钮: {label!r}')
                    return loc.first
                except Exception:
                    continue
        return None

    async def find_input(self, *hints: str, timeout: int = 5000) -> Locator | None:
        """按 placeholder/label/aria-label 找输入框"""
        for hint in hints:
            for method in [
                lambda h: self.page.get_by_placeholder(h),
                lambda h: self.page.get_by_label(h),
                lambda h: self.page.get_by_role('textbox', name=h),
                lambda h: self.page.locator(f'input[placeholder*="{h}"]'),
                lambda h: self.page.locator(f'textarea[placeholder*="{h}"]'),
            ]:
                try:
                    loc = method(hint)
                    await loc.first.wait_for(state='visible', timeout=timeout)
                    logger.debug(f'找到输入框: {hint!r}')
                    return loc.first
                except Exception:
                    continue
        return None

    async def find_menu_item(self, *labels: str, timeout: int = 8000) -> Locator | None:
        """找侧边栏/导航菜单项"""
        for label in labels:
            for sel in [
                f'li:has-text("{label}")',
                f'[class*="menu"]:has-text("{label}")',
                f'[class*="nav"]:has-text("{label}")',
                f'a:has-text("{label}")',
            ]:
                try:
                    loc = self.page.locator(sel).first
                    await loc.wait_for(state='visible', timeout=timeout)
                    logger.debug(f'找到菜单: {label!r}')
                    return loc
                except Exception:
                    continue
        return None

    async def find_list_item_with_text(self, text: str,
                                        container_hints: list[str] | None = None,
                                        timeout: int = 5000) -> Locator | None:
        """在列表/弹窗中找包含特定文字的条目"""
        containers = container_hints or [
            '[class*="dialog"]', '[class*="modal"]', '[class*="popup"]',
            '[class*="dropdown"]', '[class*="panel"]', 'body'
        ]
        for container in containers:
            for item_tag in ['li', '[class*="item"]', '[class*="node"]',
                             '[class*="option"]', 'td', 'span']:
                sel = f'{container} {item_tag}:has-text("{text}")'
                try:
                    loc = self.page.locator(sel).first
                    await loc.wait_for(state='visible', timeout=1500)
                    logger.debug(f'找到列表项: {text!r}')
                    return loc
                except Exception:
                    continue
        return None

    async def wait_for_popup(self, *keywords: str, timeout: int = 10000) -> bool:
        """等待弹窗出现（包含指定关键词之一）"""
        popup_sels = [
            '[class*="dialog"]', '[class*="modal"]',
            '[class*="popup"]',  '[class*="overlay"]',
            '[role="dialog"]',
        ]
        deadline = asyncio.get_event_loop().time() + timeout / 1000
        while asyncio.get_event_loop().time() < deadline:
            for sel in popup_sels:
                try:
                    els = await self.page.query_selector_all(sel)
                    for el in els:
                        if not await el.is_visible():
                            continue
                        text = (await el.text_content() or '')
                        if not keywords or any(kw in text for kw in keywords):
                            logger.debug(f'弹窗出现，含关键词: {keywords}')
                            return True
                except Exception:
                    pass
            await asyncio.sleep(0.3)
        return False

    async def find_upload_trigger(self, label_hints: list[str] | None = None,
                                   timeout: int = 5000) -> Locator | None:
        """找图片上传触发器（按钮或文字区域）"""
        hints = label_hints or ['上传图片', '点击上传', '添加图片', '+', '上传']
        # 先找 file input
        for sel in ['input[type="file"]', 'input[accept*="image"]']:
            try:
                loc = self.page.locator(sel).first
                await loc.wait_for(timeout=1000)
                return loc
            except Exception:
                pass
        # 再找触发按钮
        return await self.find_button(*hints, timeout=timeout)

    async def find_sku_price_inputs(self) -> list[Locator]:
        """找 SKU 表格中的价格输入框"""
        candidates = [
            'input[placeholder*="价格"]',
            'input[placeholder*="售价"]',
            '[class*="sku"] input[type="text"]',
            '[class*="sku"] input[type="number"]',
            'table input[type="text"]',
            'table input[type="number"]',
        ]
        for sel in candidates:
            els = await self.page.query_selector_all(sel)
            if els:
                logger.debug(f'找到 {len(els)} 个价格输入框')
                return [self.page.locator(sel).nth(i) for i in range(len(els))]
        return []

    async def find_sku_stock_inputs(self) -> list[Locator]:
        """找 SKU 表格中的库存输入框"""
        candidates = [
            'input[placeholder*="库存"]',
            'input[placeholder*="数量"]',
            '[class*="stock"] input',
            '[class*="inventory"] input',
        ]
        for sel in candidates:
            els = await self.page.query_selector_all(sel)
            if els:
                logger.debug(f'找到 {len(els)} 个库存输入框')
                return [self.page.locator(sel).nth(i) for i in range(len(els))]
        return []

    async def find_title_input(self) -> Locator | None:
        """找商品标题输入框"""
        return await self.find_input(
            '请输入商品标题', '标题', '宝贝标题', '商品名称', 'title', 'Title'
        )

    async def find_publish_button(self) -> Locator | None:
        """找发布/提交按钮"""
        return await self.find_button(
            '发布', '立即发布', '发布商品', '提交', '保存并发布', '确认发布'
        )

    async def find_shipping_selector(self) -> Locator | None:
        """找运费模板选择器"""
        for sel in [
            'select[class*="freight"]', 'select[class*="postage"]',
            '[class*="freight"] select', '[class*="postage"] select',
        ]:
            try:
                loc = self.page.locator(sel).first
                await loc.wait_for(state='visible', timeout=3000)
                return loc
            except Exception:
                pass
        return await self.find_button('运费模板', '选择运费模板', timeout=3000)

    async def dump_page_structure(self) -> str:
        """调试用：输出当前页面可交互元素摘要"""
        result = await self.page.evaluate("""() => {
            const out = [];
            const els = document.querySelectorAll(
                'input:not([type="hidden"]), button, select, textarea, a[href], [role="button"]'
            );
            for (const el of els) {
                if (!el.offsetParent) continue;
                out.push({
                    tag:         el.tagName,
                    type:        el.type || '',
                    text:        (el.innerText || el.value || '').trim().slice(0, 40),
                    placeholder: el.placeholder || '',
                    class:       el.className.slice(0, 60),
                    id:          el.id.slice(0, 40),
                });
            }
            return out.slice(0, 80);
        }""")
        lines = [f"  [{r['tag']}] text={r['text']!r} ph={r['placeholder']!r} "
                 f"id={r['id']!r} cls={r['class']!r}"
                 for r in result]
        return '\n'.join(lines)
