---
name: matrix-image-publisher
description: >
  矩阵图文发布：将已渲染 PNG 发布到小红书 + 微信公众号「小绿书」。
  输入为 PNG 文件 + 文案（由 evolution-cat-infographic 生产），输出为两个平台的待确认草稿。
  触发互斥：含"做/生成/生产"意图 → evolution-cat-infographic，非本 Skill。
---

# 矩阵图文发布

> 一篇内容，两个平台。MCP ChromeDevTools 浏览器自动化。PNG 由 evolution-cat-infographic 生产。

## 前置检查

```bash
# 1. MCP ChromeDevTools 已连接（list_pages 能看到两个 tab）
#    - mp.weixin.qq.com tab（小绿书，已登录）
#    - creator.xiaohongshu.com tab（小红书，已登录）

# 2. 图片 ≥2 张 PNG
ls 小绿书/card_*.png | wc -l
```

MCP Chrome 没有对应 tab → 手动在 MCP Chrome 中打开并登录。

---

## 红线（9 条已验证无效）

| 禁止 | 原因 |
|------|------|
| `#js_description.value = "..."` | 描述源是 ProseMirror[1]，不是这个 textarea |
| `__mpTitleEditor.setContent("...")` **单独用** | Vue state 更新但保存不序列化——必须 `.value` + `dispatchEvent('input')` **同时**用 |
| `Input.insertText` / `Input.dispatchKeyEvent` | 绕过框架事件系统 |
| 小绿书 file input `[0]` | 封面图，内容图用 `[1]` |
| 小绿书旧选择器 `[placeholder="..."]` | UI 已改版，标题=`#title`，描述=`.share-text__input .ProseMirror` |
| MCP `upload_file` 逐张上传 | 编辑器只计入最后 1 张（CDN 有图但编辑器不认）。两个平台都有此问题 |
| ProseMirror 换行用 `<p>` 标签 | **小绿书**保存时被剥离，必须用 `<br>`（innerHTML 设值，已验证持久化） |
| 小红书 `textContent` + `\n` 换行 | TipTap 不认 `\n`，必须 split 创建 `<p>` 元素 appendChild（与 小绿书 `<br>` innerHTML **相反**） |
| Chrome 9222 直连 + `Page.navigate` | 9222 Chrome 没有登录 cookies，编辑器 Vue 组件不挂载 |

---

## 门禁系统

**每道门 PASS 才进下一道。FAIL 停在当前门修，不许跳。每道门最多 3 retries，第 4 次仍 FAIL → 诚实边界，人工接管。**

```
Phase 1: 内容检查
  Gate 1.1 文案 (max 3 retries)
    ├─ 标题 ≤20 字？
    ├─ 正文含 emoji ≥5 个？
    ├─ 正文含 #hashtag ≥3 个？
    └─ FAIL → 补齐，不许进 Gate 1.2

  Gate 1.2 图片 (max 3 retries)
    ├─ PNG 格式？
    ├─ 数量 ≥2 张？
    └─ FAIL → 补图，不许进 Phase 2

Phase 2: 环境
  Gate 2.1 MCP Chrome (max 3 retries)
    ├─ MCP ChromeDevTools list_pages 有 mp.weixin.qq.com tab？
    ├─ MCP ChromeDevTools list_pages 有 creator.xiaohongshu.com tab？
    └─ FAIL → 手动在 MCP Chrome 打开对应页面并登录，不许进 Phase 3

Phase 3: 发布
  Gate 3.1 小绿书 (max 3 retries)
    ├─ 图片上传完成？（mmbiz.qpic.cn 背景图 unique URLs ≈ 预期）
    ├─ 标题已填？（#title.value 非空，且 __mpTitleEditor.getContent() 非空）
    ├─ 描述已填？（ProseMirror[1] textContent 非空）
    ├─ dispatchEvent('input') 已调用？
    ├─ 草稿已保存？（URL 含 appmsgid）
    └─ FAIL → 修对应步骤，不许进 Gate 3.2

  Gate 3.2 小红书 (max 3 retries)
    ├─ 图片上传完成？
    ├─ 标题已填？（div.d-input input value = 预期）
    ├─ 正文已填？（.tiptap.ProseMirror textContent > 0）
    ├─ _onSave() 返回 truthy？
    └─ FAIL → 修对应步骤，PASS 后进 Gate 3.3

  Gate 3.3 完成报告
    ├─ 小绿书草稿 ID：___
    ├─ 小红书草稿已保存
    └─ 输出：=== 矩阵发布完成 | {日期} ===
```

---

## 核心发布流程（MCP ChromeDevTools）

**这是已验证的主流程。** 所有操作通过 MCP ChromeDevTools 的 `evaluate_script` / `navigate_page` / `fill` / `click` / `select_page` 完成。

### 图片上传：fetch + DataTransfer 技巧

**基本原理**：MCP ChromeDevTools 没有 `DOM.setFileInputFiles`，但 `evaluate_script` 可以跑异步 JS。利用本地 HTTP 文件服务器 + `fetch()` + `DataTransfer` 在浏览器 JS 内构造 FileList，一次性设置到 file input。

```bash
# Step 0: 启动本地文件服务器（CORS）
python3 -c "
import http.server, os
os.chdir('D:/HHH/自媒体/进化猫-图文/AI合集/{项目文件夹}/小绿书')

class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

http.server.HTTPServer(('127.0.0.1', 8888), CORSHandler).serve_forever()
" &
```

```javascript
// 通用上传函数（两个平台都用这个）
async () => {
    const files = ['card_1.png', 'card_2.png', 'card_3.png', 'card_4.png', 'card_5.png'];
    const dt = new DataTransfer();
    for (const f of files) {
        const resp = await fetch('http://127.0.0.1:8888/' + f);
        const blob = await resp.blob();
        dt.items.add(new File([blob], f, {type: 'image/png'}));
    }
    const input = document.querySelectorAll('input[type=file]')[1]; // 小绿书[1]; 小红书只有1个用[0]
    input.files = dt.files;
    input.dispatchEvent(new Event('change', {bubbles: true}));
    return {uploaded: dt.files.length};
}
```

**上传后等 10-15 秒**让 CDN 处理。

---

### Gate 3.1: 小绿书完整流程

**DOM 架构**
```
ProseMirror[0] — title-editor__input   → 标题（#title TEXTAREA + __mpTitleEditor Vue）
ProseMirror[1] — share-text__input      → 描述源（≠ #js_description）
ProseMirror[2] — mock-iframe-body       → 正文区（图帖留空）
```

**Step 1: 导航到空白编辑器**

```javascript
// 先从当前 tab URL 取 token，拼新 URL navigate
// URL 格式: https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&createType=8&token={token}&lang=zh_CN
```

用 `navigate_page` 导航。等 5 秒让 Vue 挂载。

**Step 2: 验证编辑器就绪**

```javascript
() => ({
    title: document.getElementById('title') ? 'exists' : 'null',
    js_submit: document.getElementById('js_submit') ? 'exists' : 'null',
    fileInputs: document.querySelectorAll('input[type=file]').length,
    proLoaded: document.querySelector('.ProseMirror') ? true : false,
    existingImgs: document.querySelectorAll('[style*="mmbiz.qpic.cn"]').length
})
// 期望: {title: 'exists', js_submit: 'exists', fileInputs: ≥2, proLoaded: true, existingImgs: 0}
```

**Step 3: 上传图片**

用上面的 fetch + DataTransfer 脚本，`input[type=file]` 取 `[1]`（内容图）。等 15 秒。

**Step 4: 填标题 —— 双保险（关键！）**

```javascript
async () => {
    const TITLE = "你的标题";
    // 保险 1: Vue setContent
    if (window.__mpTitleEditor && window.__mpTitleEditor.setContent) {
        window.__mpTitleEditor.setContent(TITLE);
    }
    // 保险 2: DOM value + 多事件
    const el = document.getElementById('title');
    el.focus();
    el.value = TITLE;
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    el.dispatchEvent(new Event('blur', {bubbles: true}));
    await new Promise(r => setTimeout(r, 500));
    return {
        domValue: el.value,
        vueContent: window.__mpTitleEditor?.getContent?.()
    };
}
// 期望: domValue === TITLE && vueContent === TITLE
```

**为什么双保险**：`.value` + `input` 事件是 CDP Python 直连时的正确做法（已验证），但 MCP evaluate_script 上下文下 Vue 有时不响应。加 `setContent` 作为备份。两个同时用确保 Vue 一定能序列化。

**Step 5: 填描述 —— ProseMirror[1] innerHTML**

```javascript
async () => {
    const DESC = "描述内容<br><br>用 br 换行<br><br>#hashtag";
    const pm = document.querySelector('.share-text__input .ProseMirror');
    pm.innerHTML = DESC;
    pm.dispatchEvent(new Event('input', {bubbles: true}));
    return {descLen: pm.textContent.length};
}
```

**注意**：换行用 `<br>`，不能用 `<p>`（保存时被剥离）。

**Step 6: 保存**

```javascript
() => { document.getElementById('js_submit').click(); return 'saving...'; }
```

等 8 秒，从 URL 取 `appmsgid`：

```javascript
() => (window.location.href.match(/appmsgid=(\d+)/) || [])[1]
```

---

### Gate 3.2: 小红书完整流程

**Step 1: 切换到小红书 tab**

`select_page` → pageId 为小红书 tab。

**Step 2: 点击"上传图文"**

`take_snapshot` → 找到 "上传图文" 元素 uid → `click`。

**Step 3: 上传图片**

用 fetch + DataTransfer，但 file input 只有 1 个，取 `[0]`。等 10 秒。

验证：snapshot 出现 "图片编辑" + "5/18"。

**Step 4: 填标题**

```javascript
// 用 MCP fill 工具，或 evaluate_script:
() => {
    const el = document.querySelector('div.d-input input');
    el.value = '你的标题';
    el.dispatchEvent(new Event('input', {bubbles: true}));
}
```

**Step 5: 填正文 —— TipTap/ProseMirror `<p>` 分段**

```javascript
() => {
    const CONTENT = `段落1

段落2

段落3`;

    const el = document.querySelector('.tiptap.ProseMirror');
    if (!el) return {error: 'no tiptap editor'};
    
    el.focus();
    while (el.firstChild) el.removeChild(el.firstChild);
    
    const lines = CONTENT.split('\n');
    for (const line of lines) {
        const p = document.createElement('p');
        if (line) { p.textContent = line; }
        else { p.appendChild(document.createElement('br')); }
        el.appendChild(p);
    }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    
    return {filled: true, textLen: el.textContent.length, paragraphs: el.querySelectorAll('p').length};
}
```

**关键**：小红书用 `<p>` 分段，空行 = `<p><br></p>`。与 小绿书 `<br>` 相反！

**Step 6: 保存**

```javascript
() => {
    const el = document.querySelector('xhs-publish-btn');
    if (!el) return {error: 'no xhs-publish-btn'};
    return el._onSave?.() ? 'saved' : 'no';
}
```

`_onSave()` 返回 truthy 即保存成功。保存后页面会跳转到草稿箱，标题出现在草稿列表中即为成功。

---

## CDP Python 直连方案（备用）

**适用场景**：Chrome 9222 端口有已登录的 小绿书 tab（即 9222 Chrome 和 MCP Chrome 是同一个实例时）。

当前环境（2026-05-19）：MCP Chrome 和 9222 Chrome 是**不同实例**，9222 无登录态 → 优先用 MCP ChromeDevTools 流程。

### 小绿书

```python
"""小绿书发布：CDP Python + websocket"""
import json, time, sys, io, re, urllib.request, websockets.sync.client as ws_client
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TITLE = "标题（≤20字）"
DESC = "描述（用 <br><br> 分段）"
IMAGES = ["C:/absolute/path/card_1.png", "C:/absolute/path/card_2.png"]

tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read())
xls_tab = next(t for t in tabs if 'mp.weixin.qq.com' in t.get('url',''))
ws = ws_client.connect(xls_tab['webSocketDebuggerUrl'])

mid = 0
def send(method, params=None):
    global mid; mid += 1
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == mid:
            if 'error' in resp: print(f'ERR: {resp["error"]}')
            return resp

send('Page.enable'); send('Runtime.enable')

token = re.search(r'token=(\d+)', send('Runtime.evaluate', {
    'expression': 'window.location.href', 'returnByValue': True
})['result']['result']['value']).group(1)

send('Page.navigate', {'url': f'https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&createType=8&token={token}&lang=zh_CN'})
time.sleep(8)

# 上传 — 必须 DOM.setFileInputFiles 一次性传
send('Runtime.evaluate', {'expression': 'document.querySelectorAll("input[type=file]")[1].id = "__xls_input"'})
oid = send('Runtime.evaluate', {'expression': 'document.getElementById("__xls_input")', 'returnByValue': False})['result']['result']['objectId']
send('DOM.setFileInputFiles', {'objectId': oid, 'files': IMAGES})
send('Runtime.evaluate', {'expression': 'document.getElementById("__xls_input").dispatchEvent(new Event("change", {bubbles: true}))'})
time.sleep(12)

# 标题
tjson = json.dumps(TITLE, ensure_ascii=False)
send('Runtime.evaluate', {
    'expression': f'(async () => {{ const el = document.getElementById("title"); el.focus(); el.value = {tjson}; el.dispatchEvent(new Event("input", {{bubbles: true}})); el.blur(); }})()',
    'awaitPromise': True
})
time.sleep(0.5)

# 描述 — <br> 换行
djson = json.dumps(DESC, ensure_ascii=False)
send('Runtime.evaluate', {
    'expression': f'(async () => {{ const pm = document.querySelector(".share-text__input .ProseMirror"); pm.innerHTML = {djson}; pm.dispatchEvent(new Event("input", {{bubbles: true}})); }})()',
    'awaitPromise': True
})
time.sleep(0.5)

# 保存
send('Runtime.evaluate', {'expression': 'document.getElementById("js_submit").click()'})
time.sleep(8)

fu = send('Runtime.evaluate', {'expression': 'window.location.href', 'returnByValue': True})['result']['result']['value']
m = re.search(r'appmsgid=(\d+)', fu)
print(f'Draft: {m.group(1) if m else "FAILED"}')

send('Page.navigate', {'url': 'about:blank'})
ws.close()
```

### 小红书

```python
"""小红书发布：CDP Python + XiaohongshuPublisher"""
import json, time, sys, io, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r"D:\Openclaw\skills\redbook-skills\scripts")
from cdp_publish import XiaohongshuPublisher

pub = XiaohongshuPublisher()
pub.connect()

pub._navigate("https://creator.xiaohongshu.com/publish/publish?source=official")
pub._sleep(3)
pub._send("Emulation.setPageScaleFactor", {"pageScaleFactor": 0.8})
pub._sleep(0.5)

pub._click_image_text_tab()
pub._upload_images(IMAGES)
pub._sleep(1)

pub._fill_title(TITLE)
pub._fill_content(CONTENT)
pub._sleep(1)

print(pub._evaluate("""(() => {
    const el = document.querySelector('xhs-publish-btn');
    return el?._onSave?.() ? 'saved' : 'no';
})()"""))

pub.ws.close()
```

---

## 平台差异速查

| 维度 | 小绿书 | 小红书 |
|------|--------|--------|
| 编辑器框架 | Vue 3 + ProseMirror + UEditor | TipTap (ProseMirror) |
| 标题元素 | `#title` TEXTAREA + `__mpTitleEditor` Vue | `div.d-input input` |
| 标题填法 | `setContent()` + `.value` + `input` 事件（双保险） | `.value` + `input` 事件 |
| 描述/正文元素 | `.share-text__input .ProseMirror` (ProseMirror[1]) | `.tiptap.ProseMirror` |
| 换行方式 | `<br>` innerHTML（`<p>` 保存被剥离） | `<p>` 元素 appendChild（`\n` 不换行） |
| 图片上传 | input[type=file] **`[1]`** | input[type=file] `[0]` |
| 保存方式 | `#js_submit.click()` | `xhs-publish-btn._onSave()` |
| 保存确认 | URL 含 `appmsgid=` | `_onSave()` 返回 truthy |

---

## 故障速查

| 故障 | 处理 |
|------|------|
| 小绿书描述保存后为空 | 改了 `#js_description` → 改 ProseMirror[1] |
| 小绿书标题保存后为空 | 只用 `.value` 或只用 `setContent()` → **两者同时用**（双保险） |
| 小绿书标题填了但保存丢失 | Vue 没序列化 → 加 `setContent()` + `change` + `blur` 事件 |
| 小绿书图片上传后编辑器不显示 | 用了 MCP `upload_file` 逐张传 → 用 fetch + DataTransfer（或 CDP `DOM.setFileInputFiles`） |
| 小绿书换行保存后丢失 | 用了 `<p>` 标签或 `\n` → 用 `<br>`（innerHTML 赋值） |
| 小绿书编辑器加载不出（9222） | 9222 Chrome 无登录态 → 用 MCP ChromeDevTools 流程 |
| ProseMirror 索引混淆 | [0]=标题, [1]=描述, [2]=正文 |
| 图片只显示一张 | 小绿书 file input 用了 `[0]` → 改用 `[1]` |
| 小红书标题填不进 | 用 `div.d-input input` 选择器 |
| 小红书 _onSave 返回 no | 可能页面未加载完，等 1s 重试；返回 `true`（非 `'saved'`）也是成功 |
| 小红书换行消失 | 用了 `textContent` + `\n` → 必须 split 创建 `<p>` 元素（与 小绿书 `<br>` 相反！）|
| 小红书图片不显示 | MCP 逐张上传竞态 → 用 fetch + DataTransfer 一次性传 |
| 本地 HTTP 服务器占用 | `taskkill //PID <pid> //F` |

## 诚实边界

- **小绿书"发表"无确认弹窗**：只保存草稿（`#js_submit`），不发"发布"
- **小红书 _onPublish() 无确认**：慎用，默认只用 `_onSave()` 保存草稿
- **小绿书架构**：Vue 3 + ProseMirror + UEditor。ProseMirror[0]=标题, [1]=描述源, [2]=正文。`#js_description` 是镜像。保存按钮是 `<span id="js_submit">`
- **外部依赖**：小红书 CDP Python 方案依赖 `D:\Openclaw\skills\redbook-skills\scripts\cdp_publish.py`；MCP 方案无外部依赖
- **登录态 2h 过期**：长时间任务可能掉登录
- **Chrome 实例差异**（2026-05-19）：MCP Chrome 和 9222 Chrome 是不同实例。MCP 方案优先
- **信息截止 2026-05-19**：平台 UI 可能变化

## 参考

- `references/xiaolvshu-workflow.md` — 小绿书技术细节
- `tips/matrix-publishing-pitfalls.md` — 踩坑记录
