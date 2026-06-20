import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "../browser/automation-node/node_modules/playwright-core/index.mjs";

// Deprecated for the current project workflow.
// The fixed workflow is to use the already logged-in Playwright MCP tab, not to
// launch a separate browser/profile from this script. Keep this file only as a
// fallback if the user explicitly asks for standalone local collection.

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chromePath = path.join(rootDir, "browser", "chrome", "chrome-win64", "chrome.exe");
const profileDir = path.join(rootDir, "browser", "profile-wechat-store");
const reportDir = path.join(rootDir, "data", "wechat-store");

const pages = [
  {
    key: "transaction",
    name: "交易数据",
    url: "https://store.weixin.qq.com/shop/statistics/transaction",
  },
  {
    key: "product",
    name: "商品数据",
    url: "https://store.weixin.qq.com/shop/statistics/product",
  },
  {
    key: "crowd",
    name: "人群数据",
    url: "https://store.weixin.qq.com/shop/statistics/collect",
  },
  {
    key: "compass",
    name: "电商罗盘",
    url: "https://store.weixin.qq.com/shop-faas/mmecnodecompasscommon/thirdParty/shop/loginCompassByShop",
  },
];

const metricNames = [
  "成交金额",
  "成交订单数",
  "成交人数",
  "下单金额",
  "下单订单数",
  "下单人数",
  "客单价",
  "退款金额",
  "成交退款金额",
  "商品曝光人数",
  "商品点击人数",
  "商品点击次数",
  "成交件数",
  "点击成交率",
  "累计收藏人数",
  "收藏人数",
  "累计会员人数",
  "入会人数",
  "累计加购人数",
  "加购人数",
  "累计领券人数",
  "领券人数",
  "累计关注人数",
  "关注人数",
  "直播曝光次数",
  "短视频播放量",
  "动销达人数",
  "点击-成交转化率",
  "千次观看成交金额",
];

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return [
    d.getFullYear(),
    pad(d.getMonth() + 1),
    pad(d.getDate()),
    `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`,
  ].join("-");
}

function cleanText(text) {
  return text.replace(/\r/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

function extractMetrics(text) {
  const lines = cleanText(text).split("\n").map((line) => line.trim()).filter(Boolean);
  const metrics = {};

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!metricNames.includes(line)) continue;

    const value = lines.slice(i + 1, i + 5).find((candidate) =>
      /^(￥?\d+(?:\.\d+)?%?|￥\d+(?:\.\d+)?(?:\/1000)?|0\.00%|-100\.00%)$/.test(candidate),
    );
    if (value && metrics[line] === undefined) metrics[line] = value;
  }

  return metrics;
}

function buildSummary(collected) {
  const lines = [];
  lines.push("# 微信小店低频巡检日报");
  lines.push("");
  lines.push(`采集时间：${new Date().toLocaleString("zh-CN", { hour12: false })}`);
  lines.push("");
  lines.push("说明：本脚本只读取后台可见数据，不下载、不提交、不修改店铺设置。");
  lines.push("");

  for (const item of collected) {
    lines.push(`## ${item.name}`);
    lines.push("");
    if (item.status !== "ok") {
      lines.push(`状态：${item.status}`);
      if (item.message) lines.push(`说明：${item.message}`);
      lines.push("");
      continue;
    }

    if (item.timeRange) lines.push(`统计时间：${item.timeRange}`);
    const entries = Object.entries(item.metrics);
    if (entries.length) {
      for (const [name, value] of entries) lines.push(`- ${name}：${value}`);
    } else {
      lines.push("- 没有提取到明确指标，请查看原始文本或截图。");
    }
    if (/购买人群数量不足10人时不展示画像/.test(item.text)) {
      lines.push("- 买家人群特征：购买人群数量不足 10 人，不展示画像。");
    }
    if (/暂无数据/.test(item.text)) lines.push("- 页面包含“暂无数据”区域。");
    lines.push("");
  }

  return lines.join("\n");
}

async function waitForReadablePage(page) {
  await page.waitForLoadState("domcontentloaded", { timeout: 90000 });
  await page.waitForTimeout(4000);
}

async function readVisibleText(page) {
  const frameTexts = [];
  for (const frame of page.frames()) {
    try {
      const body = await frame.locator("body").innerText({ timeout: 5000 });
      if (body.trim()) frameTexts.push(body);
    } catch {
      // Cross-origin or not-yet-ready frames are skipped; the top page remains readable.
    }
  }

  if (frameTexts.length) return cleanText(frameTexts.join("\n\n"));
  return cleanText(await page.locator("body").innerText({ timeout: 10000 }));
}

async function main() {
  await fs.mkdir(reportDir, { recursive: true });

  const context = await chromium.launchPersistentContext(profileDir, {
    executablePath: chromePath,
    headless: false,
    viewport: { width: 1365, height: 768 },
    acceptDownloads: false,
    args: ["--no-first-run", "--no-default-browser-check", "--no-proxy-server"],
  });

  const page = context.pages()[0] ?? await context.newPage();

  if (process.argv.includes("--login")) {
    try {
      await page.goto("https://store.weixin.qq.com/", { waitUntil: "domcontentloaded", timeout: 90000 });
      console.log("请在打开的浏览器窗口完成微信小店登录。脚本最多等待 10 分钟。");

      const deadline = Date.now() + 10 * 60 * 1000;
      while (Date.now() < deadline) {
        await page.waitForTimeout(3000);
        const text = await readVisibleText(page).catch(() => "");
        if (/店铺数据|退出登录|微信小店电商罗盘|光阴童话时尚艺术馆/.test(text)) {
          console.log("登录态已保存到专用浏览器资料目录。");
          return;
        }
      }

      console.log("等待登录超时。请重新运行登录脚本。");
      process.exitCode = 1;
      return;
    } finally {
      await context.close();
    }
  }

  const collected = [];

  try {
    for (const target of pages) {
      await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 90000 });
      await waitForReadablePage(page);

      const text = await readVisibleText(page);
      const loginNeeded = /扫码|登录|请使用微信|二维码|管理我的小店/.test(text);
      const timeRange = text.match(/统计时间\s*\d{4}\/\d{2}\/\d{2}\s*至\s*\d{4}\/\d{2}\/\d{2}/)?.[0]
        ?? text.match(/近7天\s*\d{4}\/\d{2}\/\d{2}\s*-\s*\d{4}\/\d{2}\/\d{2}/)?.[0];

      collected.push({
        ...target,
        finalUrl: page.url(),
        status: loginNeeded ? "login_required" : "ok",
        message: loginNeeded ? "需要先在打开的浏览器窗口扫码或完成登录，然后重新运行脚本。" : "",
        timeRange,
        metrics: loginNeeded ? {} : extractMetrics(text),
        text: text.slice(0, 12000),
      });

      await page.waitForTimeout(3000);
    }
  } finally {
    await context.close();
  }

  const stamp = nowStamp();
  const jsonPath = path.join(reportDir, `${stamp}.json`);
  const mdPath = path.join(reportDir, `${stamp}.md`);

  await fs.writeFile(jsonPath, `\uFEFF${JSON.stringify({ generatedAt: new Date().toISOString(), collected }, null, 2)}`, "utf8");
  await fs.writeFile(mdPath, `\uFEFF${buildSummary(collected)}`, "utf8");

  console.log(`JSON: ${jsonPath}`);
  console.log(`REPORT: ${mdPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
