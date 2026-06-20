import asyncio
import json
import random
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright, BrowserContext, Page

from core.stealth_scripts import STEALTH_JS
from core.human_behavior import HumanBehavior
from core.popup_handler import PopupHandler


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.112 Safari/537.36",
]

_RESOLUTIONS = [
    (1920, 1080), (1440, 900), (1536, 864), (1366, 768),
]

_SETTINGS_FILE = Path('config/settings.json')


def _load_settings() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


class BrowserEngine:
    """
    单账号浏览器引擎。
    browser_mode = "existing"  →  通过 CDP 连接已有浏览器（推荐）
    browser_mode = "new"       →  启动独立 Chrome 持久会话
    """

    def __init__(self, account_name: str, profiles_root: str = 'profiles'):
        self.account_name = account_name
        self.profile_dir  = Path(profiles_root) / account_name
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        cfg = _load_settings()
        self._use_existing = cfg.get('browser_mode', 'existing') == 'existing'
        self._debug_port   = cfg.get('debug_port', 9222)

        # 指纹（仅新建模式使用）
        self._ua         = random.choice(_USER_AGENTS)
        self._resolution = random.choice(_RESOLUTIONS)
        self._noise_seed = random.randint(2, 99)

        self._playwright = None
        self._context: BrowserContext | None = None
        self._browser_cdp = None   # CDP 模式的浏览器对象
        self._is_cdp      = False
        self.page:  Page | None = None
        self.human: HumanBehavior | None = None
        self.popup: PopupHandler  | None = None
        self._stop_flag = False

    # ── 启动入口 ──────────────────────────────────────────────────────────────

    async def start(self) -> Page:
        self._playwright = await async_playwright().start()

        if self._use_existing:
            try:
                return await self._connect_existing()
            except Exception as e:
                raise RuntimeError(
                    f"无法连接已有浏览器 (端口 {self._debug_port})\n\n"
                    f"请先双击运行工具目录下的「启动调试浏览器.bat」，\n"
                    f"用调试模式打开浏览器并登录淘宝后，再点击开始上架。\n\n"
                    f"详情: {e}"
                ) from e
        else:
            return await self._launch_new()

    # ── 连接已有浏览器（CDP 模式）────────────────────────────────────────────

    async def _connect_existing(self) -> Page:
        cdp_url = f'http://localhost:{self._debug_port}'
        logger.info(f"[{self.account_name}] 连接已有浏览器 {cdp_url} …")

        self._browser_cdp = await self._playwright.chromium.connect_over_cdp(cdp_url)
        self._is_cdp = True

        contexts = self._browser_cdp.contexts
        if not contexts:
            ctx = await self._browser_cdp.new_context()
        else:
            ctx = contexts[0]
        self._context = ctx

        # 对话框自动关闭
        self._context.on('dialog', lambda d: asyncio.create_task(d.dismiss()))

        # 优先使用已打开的淘宝卖家页面
        pages = ctx.pages
        taobao_page = None
        for p in pages:
            if any(kw in p.url for kw in
                   ['taobao.com', 'alibaba.com', 'alimama.com', 'qianniu']):
                taobao_page = p
                break
        self.page = taobao_page or (pages[0] if pages else await ctx.new_page())

        self.human = HumanBehavior(self.page)
        self.popup = PopupHandler(
            self.page,
            on_security_stop=self._on_security,
            on_captcha_pause=self._on_captcha,
        )

        logger.info(f"[{self.account_name}] 已连接到浏览器，当前页面: {self.page.url[:60]}")
        return self.page

    # ── 新建浏览器（持久 Profile 模式）──────────────────────────────────────

    async def _launch_new(self) -> Page:
        w, h = self._resolution
        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-first-run',
            '--no-default-browser-check',
            f'--window-size={w},{h}',
            '--lang=zh-CN',
        ]

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=False,
            channel='chrome',
            args=launch_args,
            user_agent=self._ua,
            viewport={'width': w, 'height': h},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            color_scheme='light',
            ignore_https_errors=True,
        )

        init_script = f"window.__canvasNoiseSeed = {self._noise_seed};\n" + STEALTH_JS
        await self._context.add_init_script(init_script)
        self._context.on('dialog', lambda d: asyncio.create_task(d.dismiss()))

        pages = self._context.pages
        self.page = pages[0] if pages else await self._context.new_page()

        self.human = HumanBehavior(self.page)
        self.popup = PopupHandler(
            self.page,
            on_security_stop=self._on_security,
            on_captcha_pause=self._on_captcha,
        )

        logger.info(f"[{self.account_name}] 新浏览器已启动  分辨率={w}x{h}")

        if self.page.url in ('about:blank', ''):
            await self.goto('https://myseller.taobao.com/home.htm/QnworkbenchHome/')

        return self.page

    # ── 安全弹窗 / 验证码 ────────────────────────────────────────────────────

    async def _on_security(self):
        self._stop_flag = True
        logger.error(f"[{self.account_name}] 安全风控，已设置停止标志")

    async def _on_captcha(self):
        logger.warning(f"[{self.account_name}] 验证码：等待人工处理，最长 5 分钟…")
        for _ in range(300):
            await asyncio.sleep(1)
            text = await self.popup._visible_popup_text()
            if not text:
                logger.info(f"[{self.account_name}] 验证码已处理，继续任务")
                return
        logger.error(f"[{self.account_name}] 等待验证码超时，停止任务")
        self._stop_flag = True

    async def check_popups(self) -> bool:
        await self.popup.check()
        return not self._stop_flag

    async def goto(self, url: str, wait: str = 'domcontentloaded'):
        await self.page.goto(url, wait_until=wait, timeout=30000)
        await asyncio.sleep(random.uniform(0.8, 2.0))
        await self.check_popups()

    # ── 关闭 ─────────────────────────────────────────────────────────────────

    async def close(self):
        if self._is_cdp:
            # CDP 模式：仅断开连接，不关闭用户浏览器
            if self._playwright:
                await self._playwright.stop()
            logger.info(f"[{self.account_name}] 已断开浏览器连接（浏览器继续运行）")
            return
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info(f"[{self.account_name}] 浏览器已关闭")
