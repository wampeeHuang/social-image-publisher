# 小绿书（微信公众号贴图）发布 · 详细流程

## 什么是小绿书

微信公众号在 2025 年推出的「图片消息」功能（后改称「贴图」）。形态类似小红书：
- 多张图片 + 短标题 + 简短正文
- 手机端展示为卡片式信息流
- UI 限制：标题 ≤20 字，正文 ≤1000 字，图片 ≤20 张（计数器 0/20）

## 架构选择

| 优先级 | 方案 | 原理 |
|--------|------|------|
| 1 | Chrome DevTools MCP | `upload_file` + `fill` + `click`，全流程浏览器自动化 |
| 2 | 人工发布包 | 生成截图+文案，人工操作 |

**微信公众号没有公开的图片消息 API**（文章草稿有 API，图片消息没有）。MCP 是唯一自动化方案。

---

## 方案 1：CDP Python WebSocket → Chrome debug port 9223（推荐 ✅ 已验证）

### 前置条件

1. Chrome debug port 9223 可用（`http://127.0.0.1:9223/json` 可访问）
2. 浏览器已登录 https://mp.weixin.qq.com/
3. 图片已准备好（PNG，≤20 张）
4. Python `websockets` 库已安装

### 核心流程

```
Page.navigate → 贴图编辑器 URL
  → Runtime.evaluate 给 file input 设 id
  → DOM.setFileInputFiles 一次性传所有图片（多文件！）
  → dispatchEvent('change') 触发微信 JS 上传
  → 等待 5s 上传完成
  → Runtime.evaluate 填标题（≤20 字）
  → Runtime.evaluate 填描述（≤1000 字）
  → Runtime.evaluate 点击"保存为草稿"
```

### 编辑器 URL

直达贴图编辑器（跳过首页导航）：
```
https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&createType=8&token={TOKEN}&lang=zh_CN
```

`token` 从登录态获取（访问 mp.weixin.qq.com 后 URL 中可见）。

### 图片上传（关键步骤）

**2026-05-17 更新**：MCP `upload_file` 方案**可行**。虽微信 `input[type=file]` 带 `multiple: true`，但 MCP `upload_file` 每次调用实际会触发 WeChat JS 处理并持久化图片到 CDN。方法：先用 `evaluate_script` 给 file input 设可见 CSS（`position:fixed;top:50px;left:50px;border:3px solid red`），触发编辑器显示「选择文件」按钮，再对按钮 uid 逐张 `upload_file`。已验证 5 张图全部叠加成功。

**CDP 方案仍为首选**（一次性传文件更快），但 MCP 方案在 9222 端口不可用时是可靠的 fallback。

**完整上传代码**：

```python
import json, time, websockets.sync.client as ws_client

def send(ws, method, params=None):
    """Send CDP command and wait for matching response."""
    global msg_id
    msg_id += 1
    ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params or {}}))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == msg_id:
            return resp

# 1. 连接 CDP WebSocket
ws = ws_client.connect(ws_url)

# 2. 给 file input 设 id，获取 objectId
send(ws, 'Runtime.evaluate', {
    'expression': 'document.querySelectorAll("input[type=file]")[1].id = "__file_input_1"'
})
resp = send(ws, 'Runtime.evaluate', {
    'expression': 'document.getElementById("__file_input_1")',
    'returnByValue': False
})
object_id = resp['result']['result']['objectId']

# 3. 一次性设所有文件（正斜杠路径）
send(ws, 'DOM.setFileInputFiles', {
    'objectId': object_id,
    'files': [
        'C:/Users/Administrator/AppData/Local/Temp/xls_card_1.png',
        'C:/Users/Administrator/AppData/Local/Temp/xls_card_2.png',
        'C:/Users/Administrator/AppData/Local/Temp/xls_card_3.png',
        'C:/Users/Administrator/AppData/Local/Temp/xls_card_4.png',
        'C:/Users/Administrator/AppData/Local/Temp/xls_card_5.png',
    ]
})

# 4. 手动 dispatch change 事件（setFileInputFiles 不会自动触发）
send(ws, 'Runtime.evaluate', {
    'expression': '''document.getElementById("__file_input_1")
        .dispatchEvent(new Event("change", {bubbles: true}))'''
})

# 5. 等待微信异步上传到 mmbiz.qpic.cn CDN
time.sleep(5)
```

**核心约束**：

| 约束 | 说明 |
|------|------|
| **必须 CDP Python** | MCP `upload_file` 不支持多文件叠加；必须 Python `websockets` 直连 CDP |
| **文件路径** | 正斜杠（`C:/Users/...`），CDP 不接受反斜杠 |
| **objectId 非 nodeId** | `DOM.setFileInputFiles` 用 `objectId`（来自 `Runtime.evaluate` with `returnByValue: false`），`DOM.requestNode` 返回的 `nodeId` 可能为 0 |
| **手动 dispatch change** | `setFileInputFiles` 不会自动触发 change 事件 |
| **等待上传** | change 事件后微信 JS 异步上传到 CDN，需等待 5s+ |

**图片存储机制**：上传后图片以 CSS `background-image` 形式存储在 `.image-selector__bottom-list-item` 元素中，URL 域名为 `mmbiz.qpic.cn`。

### MCP 方案为什么不行（废弃记录）

微信贴图编辑器有两个 `input[type=file]`，都带有 `multiple: true`：
- `input[0]`：accepts `image/gif,image/jpeg,image/jpg,image/png,image/svg,image/webp`（封面图）
- `input[1]`：accepts `image/bmp, image/png, image/jpeg, image/jpg, image/gif, image/webp`（内容图）

~~MCP `upload_file` 每次调用只设一个文件并 dispatch change。对于 `multiple` 输入框，每次设置会替换整个 FileList——上传 card_2 时 card_1 就被清掉了。最终只剩最后一张。~~

**2026-05-17 修正**：上述结论不准确。实测 MCP `upload_file` 通过「选择文件」按钮逐张上传，WeChat JS 会逐个处理并累计到 CDN。5 张图全部叠加成功，编辑器计数器显示 5/5。

### 填标题

标题是 `#title` **TEXTAREA**（非 contenteditable div），由 `__mpTitleEditor` Vue 3 组件管理。

```python
tjson = json.dumps(TITLE, ensure_ascii=False)
send(ws, 'Runtime.evaluate', {
    'expression': f'(async () => {{ const el = document.getElementById("title"); if (el) {{ el.focus(); el.value = {tjson}; el.dispatchEvent(new Event("input", {{bubbles: true}})); el.dispatchEvent(new Event("change", {{bubbles: true}})); el.blur(); }} return "ok"; }})()',
    'awaitPromise': True
})
```

**标题核心约束**：
- 选择器：`#title` TEXTAREA（不是 `[placeholder="请在这里输入标题"]`）
- 用 `.value`（不是 `.textContent`）赋值
- `__mpTitleEditor.setContent()` 只改 Vue state，保存不序列化 → 不可用
- 标题显式 `0/20` 计数器

### 填描述（摘要）

描述源是 **ProseMirror[1]**（父容器 `.share-text__input js_pmEditorArea`）。`#js_description` textarea 是镜像，只在页面 init 时从 ProseMirror 同步。

```python
djson = json.dumps(DESC, ensure_ascii=False)
send(ws, 'Runtime.evaluate', {
    'expression': f'(async () => {{ const pm = document.querySelector(".share-text__input .ProseMirror"); if (pm) {{ pm.textContent = {djson}; pm.dispatchEvent(new Event("input", {{bubbles: true}})); pm.dispatchEvent(new Event("change", {{bubbles: true}})); }} return "ok"; }})()',
    'awaitPromise': True
})
```

**描述核心约束**：
- 选择器：`.share-text__input .ProseMirror`（ProseMirror[1]）
- **不是** `#js_description` textarea（那是镜像，修改后保存会丢）
- **120 字硬限制**：超限静默保存失败，无弹窗提示。控制在 120 字以内
- 描述显示在分享预览卡片中

### 保存草稿

保存按钮是 `<span id="js_submit">`，handler 是 webpack 闭包（函数已 minified）。

```python
send(ws, 'Runtime.evaluate', {
    'expression': "document.getElementById('js_submit').click()"
})
```

保存成功后 URL 变为 `/cgi-bin/appmsg?...&appmsgid={ID}`，其中 `appmsgid` 为草稿 ID。

**禁止点击"发表"按钮**（`draft-only` 模式红线）。

---

## 方案 2：人工发布包（降级）

当 MCP 整体不可用时，生成发布包：

```
output/YYYYMMDD_标题/
├── 小绿书_发布说明.txt
├── 封面.png
├── 配图_01.png
├── 配图_02.png
└── ...
```

**发布说明内容格式**：
```
=== 小绿书发布 ===
标题：XXX
正文：XXX

操作步骤：
1. 打开 https://mp.weixin.qq.com/
2. 点击「新的创作」→「图片消息」
3. 上传以下图片（按顺序）：封面.png, 配图_01.png, ...
4. 填写标题和正文
5. 保存草稿

图片已按上传顺序命名。
```

---

## 内容约束

| 字段 | 限制 | 说明 |
|------|------|------|
| 标题 | ≤ 20 字 | UI 显示 0/20 计数器，超长截断 |
| 正文 | ≤ 1000 字 | UI 显示 0/1000 计数器 |
| 图片 | ≤ 20 张 | UI 显示 0/20 计数器 |
| 图片格式 | PNG / JPG | PNG 推荐 |
| 图片比例 | 3:4 或 16:9 | 手机端 3:4 体验更好 |

---

## 与小红的差异

| 维度 | 小红书 | 小绿书 |
|------|--------|--------|
| 话题标签 | #标签形式，自动提取 | 不支持 |
| 标题长度 | 20 字 | 20 字 |
| 图片数量 | 最多 18 | 最多 20 |
| 发布入口 | creator.xiaohongshu.com | mp.weixin.qq.com |
| 用户群 | 年轻女性为主 | 微信全量用户 |
| 内容偏好 | 视觉冲击+生活方式 | 信息密度+实用价值 |
| 私密机制 | 发布时选"仅自己可见" | 保存草稿，不点发表 |

---

## 工匠框架：DOM 架构（2026-05-18 验证）

微信编辑器是 **Vue 3 + ProseMirror + UEditor** 混合架构。理解 DOM 结构是正确操作的前提。

### ProseMirror 三实例

```
ProseMirror[0] — 标题编辑器
  parentClass: title-editor__input
  关联: #title TEXTAREA + __mpTitleEditor Vue 组件

ProseMirror[1] — 描述/摘要编辑器（保存源）
  parentClass: share-text__input js_pmEditorArea
  关联: #js_description TEXTAREA（镜像，非源）

ProseMirror[2] — 正文区（图帖可空）
  parentClass: mock-iframe-body
  含 UEditor 占位符 widget（"从这里开始写正文"）
```

### 正确操作方式

| 目标 | 操作元素 | 方法 | 验证 |
|------|---------|------|------|
| 标题 | `#title` TEXTAREA | `.value` + `dispatchEvent('input')` | 重开检查 `#title.value` 或 `__mpTitleEditor.currentContent` |
| 描述 | `.share-text__input .ProseMirror` | `.textContent` + `dispatchEvent('input')` | 重开检查 `.share-text__input .ProseMirror` textContent |
| 上传 | `input[type=file][1]` | `DOM.setFileInputFiles` + `dispatchEvent('change')` | 检查 `[style*="mmbiz.qpic.cn"]` 数量 |
| 保存 | `#js_submit` span | `.click()` | 检查 URL 含 `appmsgid` |

### 错误操作（已验证不持久化）

| 操作 | 为什么不持久化 |
|------|--------------|
| `#js_description.value = "..."` | 描述源是 ProseMirror[1]，不是这个 textarea |
| `__mpTitleEditor.setContent("...")` | 只改 Vue state，保存不序列化 |
| `#title.textContent = "..."` | title 是 TEXTAREA，应用 `.value` |

### 关键全局变量

| 变量 | 说明 |
|------|------|
| `__mpTitleEditor` | Vue 3 组件实例（标题编辑器） |
| `wx.data` | 登录凭证：ticket, uin, user_name, nick_name |
| `UE` | UEditor 库对象（`UE.instants` 可能为空） |

---

## 常见故障

| 故障 | 排查 |
|------|------|
| 公众号登录过期 | 打开 mp.weixin.qq.com 重新扫码，登录态通常 2 小时过期 |
| 图片上传后只剩一张 | 用了 MCP `upload_file` 串行上传——改用 CDP `DOM.setFileInputFiles` 一次性传所有文件 |
| 图片上传后不显示 | 确认手动 dispatch 了 change 事件；`setFileInputFiles` 不会自动触发；等待 5s+ 让异步上传完成 |
| CDP 连接被拒 | 检查 Chrome 是否带 `--remote-allow-origins=*` 启动；用 `websockets` 库（非 `websocket`）避免 Origin 头问题 |
| `DOM.setFileInputFiles` 报错 | 文件路径用正斜杠（`C:/Users/...`）；确认用 `objectId` 参数（非 `nodeId`） |
| 「图片消息」入口找不到 | 用直达 URL（含 `type=77&createType=8`）跳过首页导航 |
| 保存草稿失败 | 检查标题是否为空、图片是否全部上传完成 |
| Chrome debug port 未启动 | `chrome.exe --remote-debugging-port=9222 --remote-allow-origins=*` |
