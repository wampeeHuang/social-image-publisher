# 矩阵图文发布

一键将内容发布到小红书 + 微信公众号「小绿书」——默认仅存草稿，安全第一。

## 架构

```
内容 md → [渲染图片卡片] → 小红书 CDP 发布 → 小绿书 CDP 发布 → 完成报告
```

**两个平台，同一套图片卡片。**

## 安全策略

- **默认仅存草稿**，绝不自动点「发布」
- **复用浏览器登录态**，不提取 Cookie 到文件
- **频率控制**，单平台连续发布 ≥ 5 分钟间隔
- **人工确认**，最终发布由用户在手机端确认

## 文件结构

```
SKILL.md                              # 执行入口
README.md                             # 本文件
requirements.txt                      # Python 依赖
scripts/
  render_xhs.py                       # Playwright 卡片渲染（13 主题）
  render_xhs.js                       # Node.js 备用渲染
  publish_xhs.py                      # 小红书 API 发布（降级方案）
assets/
  cover.html / card.html              # HTML 渲染模板
  styles.css                          # 公共样式
  themes/                             # 13 个主题 CSS
references/
  xhs-workflow.md                     # 小红书发布详细流程
  xiaolvshu-workflow.md               # 小绿书发布详细流程
.gitignore
```

## 前置条件

- Python 3.10+ / Node.js（渲染用）
- Google Chrome（CDP 浏览器自动化）
- Playwright（`pip install playwright && playwright install chromium`）
- redbook-skills（小红书 CDP 发布脚本）
- 已登录的微信公众平台 + 小红书（浏览器登录态）

## 快速开始

```bash
# 1. 渲染内容为图片卡片
python scripts/render_xhs.py article.md -t xiaohongshu -c classic -m auto-split

# 2. 发布到小红书（CDP 浏览器）
cd ../redbook-skills
python scripts/publish_pipeline.py --preview \
  --title "标题" --content "正文" \
  --images "../matrix-image-publisher/cover.png" "../matrix-image-publisher/card_1.png"

# 3. 发布到小绿书（公众号贴图）
# 使用 agent-browser 或 redbook-skills CDP 工具
# 详见 references/xiaolvshu-workflow.md
```

## 输入方式

- **标准**：Markdown 文件（含 YAML 元数据 + 正文 + 图片引用）
- **快捷**：直接给标题/正文/图片路径，自动生成 md

## 诚实边界

- 平台反自动化检测可能升级，CDP 方案不能保证 100% 稳定
- 小红书 Cookie 有效期 1-7 天，CDP 模式通过复用 Chrome Profile 延长
- 小绿书 CDP 发布流程基于 2026 年 5 月的微信公众号后台结构
- 同一篇内容在不同平台的最优表现形式不同，本 skill 不做内容改写
- 本 skill 制定于 2026-05

## 致谢

- 卡片渲染引擎来自 [Auto-Redbook-Skills](https://github.com/TecSong/Auto-Redbook-Skills)（13 主题 + 5 封面布局）
- 小红书 CDP 发布参考 [XiaohongshuSkills](https://github.com/white0dew/XiaohongshuSkills)
- 小绿书发布流程参考 [baoyu-skills](https://github.com/JimLiu/baoyu-skills)
