# 矩阵图文发布

> 一篇内容，三个平台。小绿书 + 小红书 + 抖音 — 全部通过 MCP ChromeDevTools 手动发布，草稿优先，安全第一。

## 这是谁的工具？

为 **需要多平台分发图文内容的创作者** 设计。如果你：
- 已经有渲染好的 PNG 卡片（来自 evolution-cat-infographic 或其他工具）
- 不想手动在三个平台重复上传、填标题、调排版
- 需要"默认仅存草稿"的安全策略 — 最终发布由人在手机端确认

那这是你的工具。如果你只有一个平台、或者内容不是图文卡片 → 不需要这个。

## 30 秒跑起来

```bash
git clone https://github.com/wampeeHuang/social-image-publisher.git
cd social-image-publisher
# 前置条件：MCP ChromeDevTools 已连接，三个 tab 已登录
#   - mp.weixin.qq.com（小绿书）
#   - creator.xiaohongshu.com（小红书）
#   - creator.douyin.com（抖音）
```

Agent 自动执行：文案门禁 → 图片门禁 → 环境检查 → 三平台依次发布 → 完成报告。

## 发布流水线

```
Phase 1: 内容检查
  Gate 1.1 文案：标题 ≤20 字？含 emoji ≥5？含 #hashtag ≥3？
  Gate 1.2 图片：PNG 格式？≥2 张？

Phase 2: 环境
  Gate 2.1 MCP Chrome：三个平台 tab 都已登录？
  Gate 2.2 图片服务器：http://127.0.0.1:8888 可访问？

Phase 3: 发布（串行，每平台 max 3 retries）
  Gate 3.1 小绿书 → Gate 3.2 小红书 → Gate 3.3 抖音

每道门 PASS 才进下一道。FAIL 停在当前门修，不许跳。
任一门第 4 次仍 FAIL → 诚实边界，人工接管。
```

## 安全策略

- **默认仅存草稿**：绝不自动点"发布"
- **复用浏览器登录态**：不提取 Cookie 到文件
- **频率控制**：单平台连续发布 ≥ 5 分钟间隔
- **人工确认**：最终发布由用户在手机端确认
- **抖音账号信息不入库**：`douyin_account.json` 已在 .gitignore

## 平台发布流程

### 小绿书（微信公众号贴图）
MCP ChromeDevTools → mp.weixin.qq.com → 图片上传（DataTransfer，多图同时上传）→ 标题填写（`#title.value` + `dispatchEvent('input')`）→ 描述填写（ProseMirror `<br>` innerHTML）→ 保存草稿

### 小红书
MCP ChromeDevTools → creator.xiaohongshu.com → 图片上传（fetch + DataTransfer）→ 标题/正文填写（TipTap `<p>` appendChild）→ 保存草稿

### 抖音
MCP ChromeDevTools → creator.douyin.com → 图片上传 → 填写 → 保存草稿
备用方案：Playwright 脚本（`scripts/publish_douyin.py`）

## 已验证的技术陷阱（9 条红线）

| # | 禁止 | 原因 |
|---|------|------|
| 1 | `#js_description.value = "..."` | 描述源是 ProseMirror，不是这个 textarea |
| 2 | `__mpTitleEditor.setContent()` 单独用 | Vue state 更新但保存不序列化 |
| 3 | `Input.insertText` / `Input.dispatchKeyEvent` | 绕过框架事件系统 |
| 4 | 小绿书 file input `[0]` | 封面图，内容图用 `[1]` |
| 5 | 小绿书旧选择器 `[placeholder="..."]` | UI 已改版 |
| 6 | MCP `upload_file` 逐张上传 | 编辑器只计入最后 1 张 |
| 7 | ProseMirror 换行用 `<p>` | 小绿书保存时被剥离，必须用 `<br>` |
| 8 | 小红书 `textContent` + `\n` | TipTap 不认 `\n`，必须 split 创建 `<p>` |
| 9 | Chrome 9222 直连 | 没有登录 cookies，编辑器 Vue 组件不挂载 |

每条都是实战踩出来的。不要"优化"这些方法——它们已经是验证过的唯一可行路径。

## 目录结构

```
social-image-publisher/
├── SKILL.md                          # Skill 入口：触发条件 + 门禁系统 + 发布流程
├── README.md                         # 本文件
├── .gitignore                        # douyin_account.json, _runtime/, .env
├── references/
│   ├── xhs-workflow.md               # 小红书 CDP 发布详细流程
│   ├── xiaolvshu-workflow.md         # 小绿书 CDP 发布详细流程
│   ├── douyin-workflow.md            # 抖音 CDP 发布详细流程
│   └── system-diagram.html           # 流水线可视化
├── scripts/
│   ├── publish_douyin.py             # 抖音 Playwright 备用方案
│   └── diagnose_douyin.py            # 抖音发布诊断工具
├── assets/
│   ├── cover.html / card.html        # HTML 渲染模板（来自 Auto-Redbook-Skills）
│   ├── styles.css                    # 公共样式
│   └── themes/                       # 13 个主题 CSS
└── requirements.txt                  # Python 依赖
```

## 部署（Agent 自部署指令）

```bash
git clone https://github.com/wampeeHuang/social-image-publisher.git
cd social-image-publisher
pip install -r requirements.txt
playwright install chromium
```

**依赖**：
- Python 3.10+ / Node.js
- Google Chrome（CDP 浏览器自动化）
- Playwright（`pip install playwright && playwright install chromium`）
- MCP ChromeDevTools（Claude Code 内置）

**前置条件**：三个平台在 Chrome 中已登录（Cookie 复用，不提取到文件）。

## 设计哲学

**零 API Key。** 不需要微信公众号 AppID/AppSecret，不需要小红书开放平台权限，不需要抖音开发者账号。所有发布通过浏览器完成——用 MCP ChromeDevTools 通过 CDP 操控真实的浏览器 UI。进入门槛降到最低：只要你能在浏览器里手动发布，这个 Skill 就能帮你在三个平台自动发布。

**草稿优先，安全第一。** 默认仅存草稿、绝不自动点"发布"、不提取 Cookie 到文件、人工手机端最终确认。每一条安全策略都在用便利换安全。信任边界在浏览器本身——Skill 只在浏览器里操作，发布按钮永远留给人类。

**逆向，不等待。** 不等待平台开放 API。直接研究三个平台编辑器的 DOM 架构（Vue 3+ProseMirror / TipTap / Semi Design），找到最小可用的内容注入路径。9 条红线每条记录根因 + 修复方案——"不要优化这些方法，它们已经是验证过的唯一可行路径"。

**门禁 > 流水线。** 三阶段门禁系统（内容检查 → 环境检查 → 串行发布），每道 PASS 才进下一道。FAIL 停在当前门修，不许跳。任一门第 4 次仍 FAIL → 诚实边界，人工接管。门禁设计让 Agent 不会在"看起来能过但实际上会失败"的状态下继续。

## 诚实边界

- **平台反自动化检测可能升级**：CDP 方案不能保证 100% 稳定
- **小红书 Cookie 有效期 1-7 天**：CDP 模式通过复用 Chrome Profile 延长
- **UI 结构依赖**：发布流程基于 2026 年 5 月的后台结构。平台改版可能导致选择器失效
- **抖音 Playwright 方案为备用**：首选 MCP ChromeDevTools（与另外两平台一致）
- **不做内容改写**：同一篇内容在不同平台的最优表现形式不同，本 Skill 只做发布
- **制定于 2026-05**

## 关联项目

- [evolution-cat-infographic](https://github.com/wampeeHuang/evolution-cat-infographic) — 图文卡片生产（本 Skill 的上游）
- [evolution-cat-article](https://github.com/wampeeHuang/evolution-cat-article) — 公众号长文生产

## 致谢

- 卡片渲染引擎来自 [Auto-Redbook-Skills](https://github.com/TecSong/Auto-Redbook-Skills)（13 主题 + 5 封面布局）
- 小红书 CDP 发布参考 [XiaohongshuSkills](https://github.com/white0dew/XiaohongshuSkills)
- 小绿书发布流程参考 [baoyu-skills](https://github.com/JimLiu/baoyu-skills)

## License

MIT
