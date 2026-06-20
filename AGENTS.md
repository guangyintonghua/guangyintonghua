# 微信小店运营项目规则

本项目名称：微信小店运营。

## 默认自动化方式

- 默认使用当前已经登录的 Playwright MCP 页面查看微信小店后台。
- 不新开浏览器，不新建页面，不切换到独立浏览器 profile，除非用户明确要求。
- 允许在当前已登录标签页内低频切换这些只读页面：
  - `https://store.weixin.qq.com/shop/statistics/transaction`
  - `https://store.weixin.qq.com/shop/statistics/product`
  - `https://store.weixin.qq.com/shop/statistics/collect`
  - `https://store.weixin.qq.com/shop-faas/mmecnodecompasscommon/thirdParty/shop/loginCompassByShop`
- 默认只读查看和总结数据，不下载、不提交、不修改、不删除。
- 查看频率保持低频，优先人工触发；不要做高频轮询。

## 本地排障规则

- PowerShell 读取中文文件时使用 `Get-Content -Encoding UTF8`；不要把默认终端乱码误判为文件损坏。
- 不要对整个项目直接执行无限制 `rg --files`、`Get-ChildItem -Recurse` 或类似全量扫描；浏览器 profile、缓存、截图和 MCP 输出会产生超大结果，容易导致会话卡顿或重新连接。
- 默认遵守 `.rgignore`，只检查 `AGENTS.md`、`README.md`、`scripts/`、`browser/*.cmd`、`browser/*.ps1`、`browser/*.json`、`data/wechat-store/` 等轻量文件。
- 微信小店页面正文在 iframe 内。判断是否正常工作时，不能只看外层菜单；需要读取 frame 文本，确认能看到“店铺数据 / 交易数据”“统计时间”“成交金额”等实际数据。
- `scripts/wechat-store-lowfreq-check.mjs` 是独立浏览器 profile 的旧备用脚本；默认不要用它判断当前 MCP 登录态是否正常。

## 安全边界

- 自动上架、改价、发布商品、创建优惠券、报名活动、发送客服消息、处理退款、发货、上传文件，均属于需要用户确认的动作。
- 任何付费自动化、广告投放、小店加热、小店投放、达人合作、营销活动，执行前必须向用户确认费用、目标、预算和具体动作。
- 不绕过平台风控、限流、登录、扫码、验证码或权限控制。
- 不使用非官方或规避限制的手段批量抓取、提交或模拟高频访问。

## 后续演进路线

1. 只读数据巡检：交易数据、商品数据、人群数据、电商罗盘。
2. 本地日报：整理近 7 天和近 30 天核心指标，输出运营建议。
3. 商品素材辅助：标题、卖点、详情页文案、主图建议、短视频脚本。
4. 自动上架辅助：生成字段草稿，用户确认后再进入发布流程。
5. 付费自动化辅助：生成投放方案和预算建议，用户确认后再执行。
