# 矩阵发布踩坑记录

> 每次发布失败后更新。记录根因 + 修复 + 为什么当时没发现。

---

## 2026-05-17：小绿书标题/描述保存后为空

**现象**：CDP verify 步骤显示 titleLen=11, descLen>0，但点击"保存草稿"后刷新页面标题和描述为空。

**根因**：微信贴图编辑器用 React。`el.textContent = "..."` 只改了 DOM，React 内部 state 未更新。保存草稿时 React 从内部 state 读取（空），写回 DOM 覆盖了 CDP 填入的内容。

**为什么当时没发现**：verify 步骤只检查了 DOM `textContent.length`，没有检查 React 内部 state。DOM 看起来有内容，但 React state 是空的。

**修复**：`textContent` 后加 `el.dispatchEvent(new Event('input', {bubbles: true}))` 触发 React 的合成事件系统，让它更新内部 state。

**教训**：框架驱动的编辑器（React/Vue/Angular），CDP 层面的 DOM 操作 ≠ 框架内部状态。验证步骤必须考虑框架层状态，不能只看 DOM。

---

## 2026-05-18：描述/摘要保存后为空

**现象**：设置 `#js_description.value` 并 `dispatchEvent('input')`，保存后重开描述为空。

**根因**：描述源不是 `#js_description` textarea，而是 ProseMirror[1]（`.share-text__input .ProseMirror`）。`#js_description` 是镜像 textarea，保存时数据从 ProseMirror[1] 序列化，不从 `#js_description` 读取。

**修正**：操作 `.share-text__input .ProseMirror` 的 `.textContent` + `dispatchEvent('input')`。

**教训**：框架驱动的编辑器，不能假设可见的 DOM 元素就是数据源。必须溯源到 ProseMirror/Vue state 层。

---

## 2026-05-18：小绿书标题用 Vue setContent 不持久化

**现象**：`__mpTitleEditor.setContent("物理定律是唯一硬约束")` 设置标题，Vue state 显示正确，但保存后重开标题为空。

**根因**：`__mpTitleEditor` 是 Vue 3 组件，`.setContent()` 更新 Vue 内部状态，但保存的序列化逻辑从 `#title` TEXTAREA 的 DOM value 读取，不从 Vue state 读取。

**修正**：直接用 `#title.value` + `dispatchEvent('input')` 设标题。

**教训**：框架组件方法和 DOM 操作可能对应不同的数据路径。验证持久化必须重开页面检查。

---

## 2026-05-18：小绿书 UI 再次改版 — 选择器全变

**现象**：skill 文档中的选择器全部失效：
- `[placeholder="请在这里输入标题"]` → 找不到
- `[placeholder="填写描述信息，让大家了解更多内容"]` → 找不到
- `button:contains('保存为草稿')` → 不是 button

**实际 DOM（2026-05-18）**：
- 标题：`#title` TEXTAREA
- 描述：`.share-text__input .ProseMirror`（ProseMirror[1]）
- 保存：`<span id="js_submit">`

**教训**：微信编辑器 UI 变动频繁。每次发布前应先用诊断脚本验证选择器，不要假设上次的代码还能用。

---

## 2026-05-18：描述超 120 字静默保存失败

**现象**：398 字描述填入后点击保存无反应，无任何错误提示。

**根因**：`#js_description` 的 `js_counter` 限制 120 字，但超限无弹窗。保存按钮的 webpack handler 检测到超限后静默返回。

**修正**：描述控制在 120 字以内。当前 DESC 68 字。

---

## 2026-05-17：小绿书图片上传 MCP upload_file 只能传一张

**现象**：用 MCP ChromeDevTools `upload_file` 逐张上传，最终只剩最后一张。

**原判断（错误）**：微信 input[type=file] 带 `multiple: true`，MCP `upload_file` 每次设一个文件会替换整个 FileList。

**修正后判断**：MCP `upload_file` 可以叠加，方法是先用 `evaluate_script` 曝光 file input（设 CSS 可见），触发编辑器显示"选择文件"按钮，再对按钮 uid 逐张 `upload_file`。WeChat JS 会逐个处理并累计到 CDN。

**最佳方案**：仍推荐 CDP `DOM.setFileInputFiles` 一次性传所有文件（更快）。

---

## 2026-05-18：小红书换行消失 — textContent + `\n` 不生效

**现象**：`el.textContent = "段落1\n\n段落2"` 填入小红书编辑器，保存后所有文字挤成一段，换行全部消失。

**根因**：小红书用 TipTap（ProseMirror），编辑器内部用 `<p>` 元素分段。`textContent` 只设文本节点，`\n` 不创建 DOM 分段。对比 `cdp_publish.py` 的 `_fill_content`：它 split `\n` → 每行 `document.createElement('p')` → `el.appendChild(p)`。

**为什么当时没发现**：小绿书换行用 `<br>`（innerHTML），我假设小红书也一样。但两个平台换行逻辑**相反**——小绿书 ProseMirror 剥离 `<p>` 保留 `<br>`，小红书 TipTap 需要 `<p>` 元素。

**修复**：拆 `\n` → 逐行创建 `<p>` 元素 → `appendChild`。空行创建含 `<br>` 的 `<p>`。

**教训**：不同平台的 ProseMirror/TipTap schema 不同。不能假设换行方式通用。必须先读平台对应的源码（cdp_publish.py）确认 DOM 操作方式。

---
