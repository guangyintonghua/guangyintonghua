import asyncio
import random
import math
from playwright.async_api import Page


class HumanBehavior:
    def __init__(self, page: Page):
        self.page = page
        self._last_x = random.randint(400, 900)
        self._last_y = random.randint(200, 600)

    # ── 鼠标移动（贝塞尔曲线）──────────────────────────────────────────────

    def _bezier(self, x1, y1, x2, y2, steps=None):
        if steps is None:
            dist = math.hypot(x2 - x1, y2 - y1)
            steps = max(12, min(40, int(dist / 15)))

        cp1x = x1 + (x2 - x1) * random.uniform(0.2, 0.4) + random.uniform(-60, 60)
        cp1y = y1 + (y2 - y1) * random.uniform(0.2, 0.4) + random.uniform(-60, 60)
        cp2x = x1 + (x2 - x1) * random.uniform(0.6, 0.8) + random.uniform(-60, 60)
        cp2y = y1 + (y2 - y1) * random.uniform(0.6, 0.8) + random.uniform(-60, 60)

        pts = []
        for i in range(steps + 1):
            t = i / steps
            u = 1 - t
            px = u**3*x1 + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*x2
            py = u**3*y1 + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*y2
            pts.append((px, py))
        return pts

    async def move_to(self, x: float, y: float):
        pts = self._bezier(self._last_x, self._last_y, x, y)
        for px, py in pts:
            await self.page.mouse.move(px, py)
            await asyncio.sleep(random.uniform(0.004, 0.018))
        self._last_x, self._last_y = x, y

    async def click_element(self, selector: str, timeout: int = 10000):
        el = await self.page.wait_for_selector(selector, timeout=timeout)
        box = await el.bounding_box()
        if not box:
            await el.click()
            return
        x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
        y = box['y'] + box['height'] * random.uniform(0.25, 0.75)
        await self.move_to(x, y)
        await asyncio.sleep(random.uniform(0.06, 0.18))
        await self.page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.12))
        await self.page.mouse.up()

    async def click_xy(self, x: float, y: float):
        await self.move_to(x, y)
        await asyncio.sleep(random.uniform(0.06, 0.15))
        await self.page.mouse.click(x, y)

    # ── 键盘输入（带偶发回删）────────────────────────────────────────────────

    async def type_text(self, text: str, clear_first: bool = False):
        if clear_first:
            await self.page.keyboard.press('Control+a')
            await asyncio.sleep(random.uniform(0.1, 0.2))
            await self.page.keyboard.press('Delete')
            await asyncio.sleep(random.uniform(0.15, 0.3))

        i = 0
        while i < len(text):
            ch = text[i]

            # 偶发打错（概率 2%），仅对普通字符
            if random.random() < 0.02 and ch.isprintable() and ch not in '\n\r\t':
                wrong = random.choice('qwertyuiopasdfghjklzxcvbnm')
                await self.page.keyboard.type(wrong)
                await asyncio.sleep(random.uniform(0.08, 0.25))
                await self.page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.06, 0.18))

            await self.page.keyboard.type(ch)

            # 打字间隔
            delay = random.uniform(0.08, 0.20)
            if ch in ' ，。！？,.!?':
                delay += random.uniform(0.05, 0.15)
            elif ch in '0123456789':
                delay += random.uniform(0.02, 0.06)

            # 每 8~15 个字符随机短暂停顿
            if i > 0 and i % random.randint(8, 15) == 0:
                delay += random.uniform(0.3, 0.8)

            await asyncio.sleep(delay)
            i += 1

    async def type_in(self, selector: str, text: str, clear_first: bool = True):
        await self.click_element(selector)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await self.type_text(text, clear_first=clear_first)

    # ── 滚动（分段带惯性感）──────────────────────────────────────────────────

    async def scroll(self, delta_y: int):
        steps = random.randint(3, 7)
        per_step = delta_y // steps
        for _ in range(steps):
            jitter = random.randint(-20, 20)
            await self.page.mouse.wheel(0, per_step + jitter)
            await asyncio.sleep(random.uniform(0.04, 0.12))

    async def random_scroll(self):
        direction = random.choices([1, -1], weights=[3, 1])[0]
        amount = random.randint(120, 450)
        await self.scroll(direction * amount)

    async def browse_page(self, count: int = None):
        if count is None:
            count = random.randint(1, 3)
        for _ in range(count):
            await self.random_scroll()
            await asyncio.sleep(random.uniform(0.4, 1.2))

    # ── 停顿 ────────────────────────────────────────────────────────────────

    async def pause(self, lo: float = 1.0, hi: float = 5.0):
        await asyncio.sleep(random.uniform(lo, hi))

    async def think(self):
        await asyncio.sleep(random.uniform(2.0, 5.5))

    async def between_fields(self):
        await asyncio.sleep(random.uniform(0.8, 2.5))

    async def between_products(self):
        await asyncio.sleep(random.uniform(30, 90))
