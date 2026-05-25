#!/usr/bin/env python3
"""诊断脚本：上传图片后截图，检查发布按钮状态，不实际发布"""
import asyncio, sys, json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
POST_IMAGE_URL_PATTERN = "**/creator-micro/content/post/image?**"
ACCOUNT = str(Path(__file__).parent.parent / "douyin_account.json")
IMAGES = [
    r"D:\HHH\自媒体\进化猫-图文\AI合集\20260523_女娲人物蒸馏目录\小绿书\card_1.png",
    r"D:\HHH\自媒体\进化猫-图文\AI合集\20260523_女娲人物蒸馏目录\小绿书\card_2.png",
    r"D:\HHH\自媒体\进化猫-图文\AI合集\20260523_女娲人物蒸馏目录\小绿书\card_3.png",
]
TITLE = "缺的不是答案，是角度"
NOTE = """Karpathy说"没卡就别动，你修的是跑分，不是用户的感觉"——这句话让我停下了优化6800个DOM节点，开始做这个网站。

🤖 AI思维顾问 · 🧠 41位思想者 · 🎬 多视角决策 · 🌊 开源MIT · ⚡ 永久免费

同一个问题扔给Karpathy、Bret Victor、花叔——三个人三种完全不同的答案。不是AI幻觉，是刻意设计的认知杠杆。

我把41位AI思想者的公开表达蒸馏成可直接调用的人格化思维顾问。浏览器打开就能用，不用下载App，不用注册付费。每个都标注了核心心智模型、决策启发式、适用边界、诚实局限。

怎么用：做重大决策前先问三个人。费曼看逻辑有没有洞，芒格看代价有没有算漏，塔勒布看下行有没有兜底。三个视角拼在一起，自己判断。最好的学习发生在退出角色之后。

装进Agent：下载SKILL.md放进Claude Code，工作场景直接调用。

blackcamellia.xin"""
TAGS = ["AI工具", "思维模型", "决策辅助", "开源项目", "认知升级"]

RUNTIME = Path(__file__).parent.parent / "_runtime"
RUNTIME.mkdir(exist_ok=True)


async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel=None)
        context = await browser.new_context(
            storage_state=ACCOUNT,
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        page.on("console", lambda m: print(f"  [js] {m.text[:120]}") if m.type in ("error","warn") else None)

        print("→ 导航到上传页")
        await page.goto(UPLOAD_URL, timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(RUNTIME / "diag_01_upload.png"))
        print("  截图: diag_01_upload.png")

        print("→ 点击「发布图文」")
        for attempt in range(3):
            try:
                await page.get_by_text("发布图文", exact=True).click(timeout=5000)
                print("  ✅ 点击成功")
                break
            except PlaywrightTimeout:
                print(f"  ⚠️ 第{attempt+1}次未找到「发布图文」")
                if attempt == 2:
                    await page.screenshot(path=str(RUNTIME / "diag_fail_no_button.png"))
                    print("  截图: diag_fail_no_button.png")
                    await browser.close()
                    return
                await page.wait_for_timeout(2000)

        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(RUNTIME / "diag_02_after_switch.png"))
        print("  截图: diag_02_after_switch.png")

        print("→ 上传图片")
        file_input = page.locator("div[class^='container'] input[accept*='image']")
        await file_input.set_input_files(IMAGES)

        try:
            await page.wait_for_url(POST_IMAGE_URL_PATTERN, timeout=60000)
            print("  ✅ URL 跳转到编辑页")
        except PlaywrightTimeout:
            print("  ❌ 上传超时")
            await page.screenshot(path=str(RUNTIME / "diag_fail_upload.png"))
            await browser.close()
            return

        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(RUNTIME / "diag_03_after_upload.png"))
        print("  截图: diag_03_after_upload.png")
        print(f"  当前URL: {page.url}")

        print("→ 填标题")
        try:
            title_input = page.locator('input[type="text"]').first
            await title_input.click()
            await title_input.fill(TITLE[:30])
            await page.wait_for_timeout(500)
            print("  ✅ 标题填写完成")
        except Exception as e:
            print(f"  ❌ 标题填写失败: {e}")

        print("→ 填描述")
        try:
            editor = page.locator('.zone-container[contenteditable="true"]')
            await editor.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await editor.type(NOTE[:200])  # 只填前200字诊断
            await page.wait_for_timeout(500)
            print("  ✅ 描述填写完成")
        except Exception as e:
            print(f"  ❌ 描述填写失败: {e}")

        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(RUNTIME / "diag_04_filled.png"))
        print("  截图: diag_04_filled.png")

        # 检查发布按钮
        print("→ 检查发布按钮")
        btn = page.get_by_role("button", name="发布", exact=True)
        btn_count = await btn.count()
        print(f"  按钮数量: {btn_count}")
        if btn_count > 0:
            is_disabled = await btn.first.is_disabled()
            is_visible = await btn.first.is_visible()
            print(f"  disabled={is_disabled}, visible={is_visible}")
            # 获取按钮文本和class
            btn_text = await btn.first.text_content()
            btn_class = await btn.first.get_attribute("class")
            print(f"  text='{btn_text}', class='{btn_class}'")

        # 也检查其他可能的发布按钮
        all_btns = page.locator("button")
        btn_texts = []
        for i in range(min(await all_btns.count(), 20)):
            t = await all_btns.nth(i).text_content()
            if t and t.strip():
                btn_texts.append(t.strip())
        print(f"  页面所有按钮: {btn_texts}")

        await page.screenshot(path=str(RUNTIME / "diag_05_buttons.png"))
        print("  截图: diag_05_buttons.png")

        print("\n→ 尝试点击发布并监听URL变化（等15秒）")
        current_url = page.url
        print(f"  点击前URL: {current_url}")

        await btn.first.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(RUNTIME / "diag_06_after_click.png"))
        print(f"  点击后URL: {page.url}")
        print("  截图: diag_06_after_click.png")

        # 等待看是否有弹窗或跳转
        for i in range(13):
            await page.wait_for_timeout(1000)
            new_url = page.url
            if new_url != current_url:
                print(f"  URL变化 ({i+1}s): {new_url}")
                current_url = new_url
            # 检查弹窗
            dialogs = page.locator('[role="dialog"], .semi-modal, .semi-popconfirm')
            if await dialogs.count() > 0:
                dialog_text = await dialogs.first.text_content()
                print(f"  弹窗出现: {dialog_text[:200]}")
                await page.screenshot(path=str(RUNTIME / f"diag_dialog_{i}.png"))
                break

        await page.screenshot(path=str(RUNTIME / "diag_07_final.png"))
        print(f"  最终URL: {page.url}")
        print("  截图: diag_07_final.png")

        print("\n诊断完成。截图在 _runtime/ 目录。")
        input("按 Enter 关闭浏览器...")
        await browser.close()


asyncio.run(diagnose())
