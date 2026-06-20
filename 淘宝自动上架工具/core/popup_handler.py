import asyncio
from enum import Enum, auto
from loguru import logger
from playwright.async_api import Page


class PopupType(Enum):
    SECURITY = auto()   # 立即停止
    CAPTCHA  = auto()   # 暂停等人工
    AD       = auto()   # 自动关闭
    NOTICE   = auto()   # 自动关闭


_SECURITY_KW = ['账号异常', '风险提示', '访问受限', '账号被限制', '异常登录',
                '安全验证失败', '封禁', '违规', '账号风险', '异常访问', '访问异常',
                '您的账号', '操作异常', '触发安全']

_CAPTCHA_KW  = ['滑块', '验证码', '短信验证', '拖动', '请完成验证',
                '安全验证', '图形验证', '请输入验证码', '人机验证', '拼图']

_CLOSE_TEXTS = ['×', '✕', '✖', 'X', '关闭', '取消', '稍后', '知道了',
                '我知道了', '不了', '关闭弹窗', '关闭广告', '跳过', '忽略',
                '暂不', '以后再说', 'close', 'Close', '×']

_POPUP_SELECTORS = [
    '.next-dialog-wrapper', '.next-overlay-wrapper',
    '[class*="modal"][style*="display: block"]',
    '[class*="modal"][style*="display:block"]',
    '[class*="dialog"]', '[class*="popup"]',
    '.J_LayerModal', '[id*="dialog"]',
    '[id*="modal"]', '[id*="popup"]',
    '.rax-view-v2[style*="position: fixed"]',
]

# 这些类的元素不是真正的弹窗（页面常驻悬浮控件 或 功能性抽屉）
_IGNORE_CLS_KEYWORDS = ['PendantWrapper', 'next-affix', 'scenario',
                         'sku-decouple-drawer', 'sell-component-image-v2-media-popup']


class PopupHandler:
    def __init__(self, page: Page,
                 on_security_stop=None,
                 on_captcha_pause=None):
        self.page = page
        self._on_security_stop = on_security_stop
        self._on_captcha_pause = on_captcha_pause

    async def check(self) -> PopupType | None:
        text = await self._visible_popup_text()
        if text is None:
            return None
        ptype = self._classify(text)
        logger.debug(f"检测到弹窗[{ptype.name}]: {text[:60]!r}")
        await self._handle(ptype, text)
        return ptype

    def _classify(self, text: str) -> PopupType:
        if any(kw in text for kw in _SECURITY_KW):
            return PopupType.SECURITY
        if any(kw in text for kw in _CAPTCHA_KW):
            return PopupType.CAPTCHA
        return PopupType.AD  # 广告/提示统一自动关闭

    async def _handle(self, ptype: PopupType, text: str):
        if ptype == PopupType.SECURITY:
            logger.error(f"安全/风控弹窗，立即停止！内容：{text[:80]!r}")
            await self._screenshot('security')
            if self._on_security_stop:
                await self._on_security_stop()

        elif ptype == PopupType.CAPTCHA:
            logger.warning("验证码弹窗，暂停等待人工处理…")
            await self._screenshot('captcha')
            if self._on_captcha_pause:
                await self._on_captcha_pause()

        else:
            await self._auto_close()

    async def _auto_close(self):
        closed = await self.page.evaluate(
            """(closeTexts) => {
                const all = document.querySelectorAll(
                    'button, a, span, div, i, [role="button"]'
                );
                for (const el of all) {
                    if (el.offsetParent === null) continue;
                    const t = (el.getAttribute('aria-label') || el.innerText || el.textContent || '').trim();
                    if (closeTexts.includes(t)) {
                        try {
                            if (typeof el.click === 'function') {
                                el.click();
                            } else {
                                el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                            }
                            return true;
                        } catch(e) { continue; }
                    }
                }
                return false;
            }""",
            _CLOSE_TEXTS
        )
        if closed:
            logger.info("弹窗已自动关闭")
        else:
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.3)
            logger.info("弹窗已用 Escape 关闭")

    async def _visible_popup_text(self) -> str | None:
        for sel in _POPUP_SELECTORS:
            try:
                text = await self.page.evaluate(
                    """([sel, ignoreCls]) => {
                        const el = document.querySelector(sel);
                        if (!el) return null;
                        // 忽略常驻悬浮控件（非弹窗）
                        const cls = el.className || '';
                        if (ignoreCls.some(kw => cls.includes(kw))) return null;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') return null;
                        if (el.offsetWidth === 0 && el.offsetHeight === 0) return null;
                        // 弹窗应靠近视口中心，忽略偏右侧的悬浮组件
                        const rect = el.getBoundingClientRect();
                        if (rect.left > window.innerWidth * 0.85) return null;
                        return el.innerText || '';
                    }""",
                    [sel, _IGNORE_CLS_KEYWORDS]
                )
                if text and text.strip():
                    return text.strip()
            except Exception:
                continue
        return None

    async def _screenshot(self, label: str):
        try:
            import time, pathlib
            path = pathlib.Path('screenshots') / f'{label}_{int(time.time())}.png'
            path.parent.mkdir(exist_ok=True)
            await self.page.screenshot(path=str(path), full_page=False)
            logger.info(f"截图已保存: {path}")
        except Exception as e:
            logger.warning(f"截图失败: {e}")
