# 小红书图文发布 · 详细流程

## 架构选择

### 生产级 vs Demo 级

小红书没有公开 API、没有 OAuth、没有 API Key。两种自动化方案有本质区别：

| | CDP 浏览器自动化 | Cookie 调内部 API |
|---|---|---|
| **原理** | Chrome DevTools Protocol 控制浏览器，模拟人工操作网页 UI | 提取 Cookie，调小红书内部 HTTP API |
| **API 隐性变化的抵抗力** | **强**。交互的是网页 UI——只要人工还能发，CDP 就能发 | **弱**。调的是未公开的内部 API——参数/签名/返回格式随时可能静默变化 |
| **登录持久性** | Chrome Profile 持久化，一次扫码用数周 | Cookie 1-7 天过期，过期不通知 |
| **故障可调试性** | snapshot 看页面状态，故障可见 | API 报错无意义，不知道具体哪里变了 |
| **级别** | ✅ 生产级 | ❌ Demo 级——适合快速验证，不适合持续运行 |

**结论**：CDP 是唯一生产方案。Cookie API 仅作为紧急降级。

两套方案，按优先级：

| 优先级 | 方案 | 适用场景 |
|--------|------|---------|
| 1 | CDP 浏览器自动化 | 日常发布（唯一推荐） |
| 2 | Cookie API 发布 | CDP 整体不可用时的紧急降级 |

---

## 方案 1：CDP 浏览器自动化（redbook-skills）

### 前置条件

1. Chrome 已安装
2. redbook-skills 已安装（`D:\Openclaw\skills\redbook-skills\`）
3. Python 依赖已安装：`pip install -r requirements.txt`

### Step 1：启动 Chrome debug 模式

```bash
python scripts/chrome_launcher.py
```

默认启动在 `127.0.0.1:9222`。

如需连接远程 Chrome：
```bash
python scripts/cdp_publish.py --host 10.0.0.12 --port 9222 check-login
```

### Step 2：检查登录状态

```bash
python scripts/cdp_publish.py check-login
```

- 已登录 → 继续下一步
- 未登录 → 弹出浏览器窗口，用户扫码登录
- 二维码模式：`python scripts/cdp_publish.py get-login-qrcode`（返回 Base64 二维码）

登录状态缓存 12 小时。

### Step 3：发布图文

```bash
# 预览模式（仅填充，不点发布）—— 推荐
python scripts/publish_pipeline.py --preview \
  --title "标题（≤20字）" \
  --content "正文内容" \
  --images "/abs/path/cover.png" "/abs/path/card_1.png"

# 无头自动发布（需 auto-publish 模式授权）
python scripts/publish_pipeline.py --headless \
  --title "标题" \
  --content "正文" \
  --image-urls "https://example.com/cover.png"
```

### 关键参数

| 参数 | 说明 |
|------|------|
| `--preview` | 填充内容后停在发布页，不点发布 |
| `--headless` | 无头模式，后台运行 |
| `--title` | 标题（≤20 字） |
| `--content` | 正文，支持 `#标签` 放在末尾行 |
| `--images` | 本地图片路径 |
| `--image-urls` | 图片 URL |
| `--account` | 多账号模式指定账号 |

### 标题长度计算规则

- 中文字符、中文标点：按 2 计
- 英文、数字、空格：按 1 计
- 总长度 ≤ 38（对应约 19-20 个中文字）

### 话题标签

在正文最后一行放入 `#标签`，会自动提取为话题：
```
这是正文内容...

#AI工具 #效率提升 #小红书干货
```

最多 10 个标签。

---

## 方案 2：Cookie API 发布（紧急降级，不保证可用）

### 前置条件

1. 获取小红书 Cookie
2. 配置 `.env` 文件：`XHS_COOKIE=your_cookie_string`
3. 安装依赖：`pip install xhs python-dotenv requests`

### Cookie 获取方式

1. 浏览器登录 https://www.xiaohongshu.com
2. F12 → Application → Cookies → 复制完整 Cookie 字符串
3. 必需字段：`a1`、`web_session`

### 发布命令

```bash
# 仅自己可见（推荐先预览）
python scripts/publish_xhs.py --title "标题" --desc "正文" --images cover.png card_1.png --private

# 公开
python scripts/publish_xhs.py --title "标题" --desc "正文" --images cover.png card_1.png

# 仅验证不发布
python scripts/publish_xhs.py --title "标题" --desc "正文" --images cover.png card_1.png --dry-run
```

---

## Vue 3 Custom Element 发布按钮（2026-05-16 发现）

小红书创作者中心的发布按钮是 `<xhs-publish-btn>` Vue 3 自定义元素。该元素有以下特点：

- **DOM 内没有子元素**：`innerHTML: ""`, `children: 0`，按钮 UI 由 Vue 内部渲染
- **Vue 3 生产构建不暴露组件引用**：`__vue__`、`__vnode__`、`_vnode` 均为 null/undefined
- **直接属性可用**：`Object.getOwnPropertyNames(el)` 返回 `['_sr', '_app', '_props', '_onPublish', '_onSave']`

**发布方法**（2026-05-16 实测成功）：

```javascript
// 获取元素
var el = document.querySelector('xhs-publish-btn');

// 直接调用 _onPublish() 触发发布
// 返回 true 表示成功，页面会跳转到 /publish/success
var result = el._onPublish();
```

**重要注意**：
- 传统 `el.click()`、CDP 鼠标点击坐标、`dispatchEvent(new MouseEvent('click'))` 均无效
- 元素位置（265,1188,680,90）内只包含"定时发布"切换，无实际发布按钮
- `_onSave()` 可用于暂存草稿，`_onPublish()` 触发发布

---

## 常见故障

| 故障 | 排查 |
|------|------|
| 发布按钮点击无反应 | 不要用 `click()`——用 `document.querySelector('xhs-publish-btn')._onPublish()` 直接调用 |
| 选择器失效 | 检查 `scripts/cdp_publish.py` 中的 `SELECTORS`，更新发布按钮/上传输入框选择器 |
| 登录过期 | `python scripts/cdp_publish.py login` 重新扫码 |
| 多图上传等待不足 | 增加 CDP 脚本中的 upload wait time |
| 图片格式不支持 | 转 PNG（小红书最佳支持） |
| Cookie 签名失败 | Cookie 过期或缺少 a1/web_session 字段，重新获取 |
