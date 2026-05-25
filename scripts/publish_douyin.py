#!/usr/bin/env python3
"""
抖音图文发布脚本 — Playwright 浏览器自动化
参考: dreammis/social-auto-upload (DouYinNote)

使用方法:
    # 首次使用：扫码登录生成 cookie 文件
    python publish_douyin.py --login --account douyin_account.json

    # 发布图文
    python publish_douyin.py \
        --account douyin_account.json \
        --title "缺的不是答案，是角度" \
        --note "Karpathy说：没卡就别动..." \
        --tags AI工具 思维模型 决策辅助 \
        --images D:/HHH/自媒体/进化猫-图文/AI合集/20260523_女娲人物蒸馏目录/小绿书/card_1.png ...

    # 定时发布
    python publish_douyin.py --account douyin_account.json --title "..." --note "..." \
        --images ... --schedule "2026-05-25 09:00"

依赖:
    pip install playwright && playwright install chromium
"""

import argparse
import asyncio
import json
import os
import sys
import re

# Windows 终端 GBK 编码无法输出 emoji，强制 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("缺少 playwright，安装中...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


# ── 常量 ──────────────────────────────────────────

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
POST_IMAGE_URL_PATTERN = "**/creator-micro/content/post/image?**"
MANAGE_URL_PATTERN = "**/creator-micro/content/manage?enter_from=publish**"
TIMEOUT = 30_000  # ms
POLL_INTERVAL = 0.5  # seconds


# ── Cookie / 登录 ─────────────────────────────────

async def _qrcode_login(account_file: str, headless: bool = False) -> bool:
    """扫码登录 → 保存 storage_state 到 account_file"""
    print("\n📱 正在打开抖音创作者登录页...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel=None)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            permissions=["geolocation"],
        )
        page = await context.new_page()

        try:
            await page.goto("https://creator.douyin.com/", timeout=TIMEOUT)
            await page.wait_for_timeout(3000)

            # 查找二维码图片
            qr_img = page.locator('img[aria-label="二维码"]')
            # 备用：扫码登录 tab 后的二维码
            if not await qr_img.is_visible(timeout=5000):
                await page.get_by_text("扫码登录").click()
                await page.wait_for_timeout(1000)

            print("📱 请使用抖音 APP 扫描屏幕上显示的二维码...")
            print("   (如果看不到二维码，请设置 headless=False 或手动打开浏览器)\n")

            # 等待登录完成（最多 180 秒）
            max_checks = 60
            for i in range(max_checks):
                await page.wait_for_timeout(3000)
                current_url = page.url

                # 检查登录标记
                login_tabs = page.locator('text=手机号登录, text=扫码登录')
                if await login_tabs.count() == 0:
                    # 登录标记消失 → 可能已登录
                    pass

                if "creator-micro/home" in current_url:
                    print("✅ 扫码登录成功！")
                    await page.wait_for_timeout(2000)
                    await context.storage_state(path=account_file)
                    print(f"💾 Cookie 已保存到: {account_file}")
                    return True

                if i % 10 == 0 and i > 0:
                    print(f"   等待中... ({i * 3}s / 180s)")

            print("❌ 登录超时")
            return False

        finally:
            await context.close()
            await browser.close()


async def cookie_auth(account_file: str) -> bool:
    """验证 cookie 是否有效"""
    if not os.path.exists(account_file):
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel=None)
        context = await browser.new_context(storage_state=account_file)
        page = await context.new_page()

        try:
            await page.goto(UPLOAD_URL, timeout=TIMEOUT)
            await page.wait_for_timeout(3000)

            # 如果页面上有 "手机号登录" 或 "扫码登录" 文案 → cookie 失效
            login_text = page.locator('text=手机号登录, text=扫码登录')
            if await login_text.count() > 0:
                return False
            return True
        except PlaywrightTimeout:
            return False
        finally:
            await context.close()
            await browser.close()


async def ensure_login(account_file: str, headless: bool = False) -> bool:
    """确保已登录：先验证 cookie，失效则扫码"""
    if await cookie_auth(account_file):
        print(f"✅ Cookie 有效: {account_file}")
        return True

    print(f"⚠️ Cookie 无效或不存在: {account_file}")
    print("📱 进入扫码登录流程...")
    return await _qrcode_login(account_file, headless=headless)


# ── 图文发布 ──────────────────────────────────────

def validate_images(image_paths: List[str]) -> List[str]:
    """验证图片文件"""
    valid = []
    for p in image_paths:
        path = Path(p)
        if not path.exists():
            print(f"⚠️ 跳过不存在的文件: {p}")
            continue
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            print(f"⚠️ 跳过非图片文件: {p}")
            continue
        valid.append(str(path.absolute()))

    if len(valid) > 35:
        print(f"⚠️ 图片超过 35 张上限，截取前 35 张")
        return valid[:35]
    return valid


async def upload_note(
    account_file: str,
    title: str,
    note: str,
    image_paths: List[str],
    tags: Optional[List[str]] = None,
    schedule_time: Optional[str] = None,
    headless: bool = True,
    debug: bool = False,
) -> dict:
    """
    发布抖音图文

    Returns:
        {"success": bool, "url": str | None, "error": str | None}
    """
    # 前置验证
    if not title:
        return {"success": False, "error": "标题不能为空"}
    if not image_paths:
        return {"success": False, "error": "图片列表不能为空"}

    images = validate_images(image_paths)
    if not images:
        return {"success": False, "error": "没有有效的图片文件"}

    print(f"\n📷 {len(images)} 张图片")
    print(f"📝 标题: {title[:30]}")
    print(f"📄 正文: {note[:50]}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            channel=None,
        )
        context = await browser.new_context(
            storage_state=account_file,
            viewport={"width": 1280, "height": 800},
            permissions=["geolocation"],
        )
        page = await context.new_page()

        if debug:
            page.on("console", lambda msg: print(f"  [console] {msg.text}"))

        try:
            # Step 1: 导航到上传页
            print("🌐 导航到上传页...")
            await page.goto(UPLOAD_URL, timeout=TIMEOUT)
            await page.wait_for_timeout(3000)

            # Step 2: 切换到图文模式（含重试）
            print("🖼️ 切换到图文模式...")
            switch_ok = False
            for attempt in range(3):
                if attempt > 0:
                    print(f"  🔄 重试切换图文模式 ({attempt + 1}/3)...")
                    await page.wait_for_timeout(2000)
                try:
                    await page.get_by_text("发布图文", exact=True).click(timeout=5000)
                    await page.wait_for_timeout(1000)
                    switch_ok = True
                    break
                except PlaywrightTimeout:
                    if attempt == 2:
                        return {"success": False, "error": "找不到「发布图文」按钮，3次重试均失败，页面可能已改版"}

            # Step 3: 上传图片
            print("📤 上传图片...")
            file_input = page.locator("div[class^='container'] input[accept*='image']")
            await file_input.set_input_files(images)

            # 等待上传完成 + URL 跳转到编辑页
            try:
                await page.wait_for_url(POST_IMAGE_URL_PATTERN, timeout=60_000)
                print("✅ 图片上传完成")
            except PlaywrightTimeout:
                return {"success": False, "error": "图片上传超时，URL 未跳转"}

            await page.wait_for_timeout(2000)

            # Step 4: 填标题和描述
            print("✍️ 填写标题和描述...")
            fill_errors = await _fill_title_and_description(page, title, note, tags or [])
            if fill_errors:
                return {"success": False, "error": f"填充失败: {'; '.join(fill_errors)}"}

            # Step 5: 定时发布（可选）
            if schedule_time:
                print(f"⏰ 设置定时发布: {schedule_time}")
                await _set_schedule_time(page, schedule_time)

            # Step 6: 发布（含重试）
            print("🚀 点击发布...")
            result = await _click_publish_with_retry(page, max_retries=3)
            if not result["success"]:
                return result

            # 保存可能会更新的 cookie
            await context.storage_state(path=account_file)

            result["title"] = title[:30]
            result["images"] = len(images)
            _write_result_file(result, account_file)

            print("✅ 发布成功！")
            return result

        except Exception as e:
            if debug:
                import traceback
                traceback.print_exc()
            error_result = {"success": False, "error": str(e)}
            _write_result_file(error_result, account_file)
            return error_result
        finally:
            await context.close()
            await browser.close()


async def _dismiss_dialogs(page):
    """关闭页面上可能存在的弹窗（如「共创中心」公告弹窗）"""
    selectors = [
        'button:has-text("我知道了")',
        'button:has-text("关闭")',
        '[role="dialog"] button:has-text("确定")',
        '.semi-modal button:has-text("确定")',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                await page.wait_for_timeout(500)
                print(f"  ✅ 关闭弹窗: {sel}")
        except Exception:
            pass


async def _click_publish_with_retry(page, max_retries: int = 3) -> dict:
    """点击发布按钮并等待跳转，支持重试。弹窗在点击后出现，需点击后立即轮询关闭。"""
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"  🔄 重试发布 ({attempt + 1}/{max_retries})...")
            await page.wait_for_timeout(2000)

        try:
            # Fresh reference every attempt
            publish_btn = page.get_by_role("button", name="发布", exact=True)
            await publish_btn.click()

            # 点击后轮询弹窗，支持多轮弹窗
            for dialog_round in range(5):  # 最多处理 5 轮弹窗
                await page.wait_for_timeout(800)
                dismissed = False
                for sel in [
                    'button:has-text("我知道了")',
                    'button:has-text("关闭")',
                    '[role="dialog"] button:has-text("确定")',
                    '.semi-modal button:has-text("确定")',
                    '.semi-modal button:has-text("确认")',
                    'button:has-text("确认发布")',
                ]:
                    try:
                        btn = page.locator(sel)
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click()
                            await page.wait_for_timeout(500)
                            print(f"  ✅ 关闭弹窗: {sel}")
                            dismissed = True
                            break
                    except Exception:
                        pass
                if dismissed:
                    # 弹窗关闭后，用小延迟再点发布（用 fresh reference）
                    await page.wait_for_timeout(800)
                    fresh_btn = page.get_by_role("button", name="发布", exact=True)
                    await fresh_btn.click()
                    continue  # 继续检查下一轮弹窗
                else:
                    break  # 没有弹窗了，发布应该在进行中

            await page.wait_for_url(MANAGE_URL_PATTERN, timeout=60_000)
            return {
                "success": True,
                "url": page.url,
            }
        except PlaywrightTimeout:
            last_error = "发布超时，URL 未跳转到管理页"
            error_text = page.locator('text=发布失败, text=参数错误, text=内容违规')
            if await error_text.count() > 0:
                msg = await error_text.first.text_content()
                return {"success": False, "error": f"发布失败: {msg}"}

    return {"success": False, "error": f"{last_error}（{max_retries}次重试）"}


def _write_result_file(result: dict, account_file: str):
    """写发布结果到 _runtime/douyin_result.json"""
    skill_dir = Path(__file__).resolve().parent.parent
    runtime_dir = skill_dir / "_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    result_file = runtime_dir / "douyin_result.json"
    result["account"] = Path(account_file).name
    result["timestamp"] = datetime.now().isoformat()

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"📄 结果已写入: {result_file}")


async def _fill_title_and_description(page, title: str, note: str, tags: List[str]) -> List[str]:
    """填充标题、描述、标签。返回错误列表，空列表 = 全部成功。"""
    errors = []

    # 标题输入框
    try:
        title_input = page.locator('input[type="text"]').first
        await title_input.click()
        await title_input.fill("")
        await title_input.fill(title[:30])  # 抖音标题限制 30 字
        await page.wait_for_timeout(500)
    except Exception as e:
        errors.append(f"标题填充失败: {e}")

    # 描述：contenteditable 区域
    editor = None
    try:
        editor = page.locator('.zone-container[contenteditable="true"]')
        await editor.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        await editor.type(note)
        await page.wait_for_timeout(500)
    except Exception as e:
        errors.append(f"描述填充失败: {e}")

    # 标签：在描述末尾加 #tag
    if tags and editor is not None:
        try:
            await editor.click()
            await page.keyboard.press("End")
            for tag in tags:
                tag = tag.strip().lstrip("#")
                if tag:
                    await editor.type(f" #{tag}")
                    await page.wait_for_timeout(100)
            await page.wait_for_timeout(500)
        except Exception as e:
            errors.append(f"标签填充失败: {e}")

    return errors


async def _set_schedule_time(page, schedule_time: str):
    """设置定时发布时间"""
    try:
        # 点击"定时发布" radio
        schedule_radio = page.locator("[class^='radio']:has-text('定时发布')")
        await schedule_radio.click()
        await page.wait_for_timeout(500)

        # 填写时间
        date_input = page.locator('.semi-input[placeholder="日期和时间"]')
        await date_input.click()
        await page.keyboard.press("Control+KeyA")
        await date_input.type(schedule_time)
        await page.wait_for_timeout(500)
    except Exception as e:
        print(f"  ⚠️ 定时设置异常: {e}")


# ── CLI ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="抖音图文发布 — Playwright 浏览器自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 扫码登录
  python publish_douyin.py --login --account douyin.json

  # 发布图文
  python publish_douyin.py --account douyin.json \\
      --title "缺的不是答案，是角度" \\
      --note "Karpathy说：没卡就别动..." \\
      --tags AI工具 思维模型 \\
      --images card_1.png card_2.png card_3.png

  # 定时发布
  python publish_douyin.py --account douyin.json \\
      --title "标题" --note "正文" --images *.png \\
      --schedule "2026-05-25 09:00"
        """,
    )

    # 登录
    parser.add_argument("--login", action="store_true", help="仅扫码登录，保存 cookie")
    parser.add_argument("--validate", action="store_true", help="仅验证 cookie 有效性，不发布")

    # 账号
    parser.add_argument("--account", type=str, default="douyin_account.json",
                        help="Cookie / storage_state 文件路径 (默认: douyin_account.json)")

    # 内容
    parser.add_argument("--title", type=str, help="标题 (≤30字)")
    parser.add_argument("--note", type=str, help="正文内容")
    parser.add_argument("--tags", nargs="*", default=[], help="标签列表")
    parser.add_argument("--images", nargs="+", default=[], help="图片文件路径")

    # 发布选项
    parser.add_argument("--schedule", type=str, help="定时发布时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True,
                        help="无头模式 (默认开启)")
    parser.add_argument("--debug", action="store_true", help="调试模式")

    args = parser.parse_args()

    if args.login:
        account_file = os.path.abspath(args.account)
        success = asyncio.run(_qrcode_login(account_file, headless=not args.headless))
        sys.exit(0 if success else 1)

    account_file = os.path.abspath(args.account)

    if args.validate:
        valid = asyncio.run(cookie_auth(account_file))
        print("✅ Cookie 有效" if valid else "⚠️ Cookie 无效")
        sys.exit(0 if valid else 1)

    if not args.title or not args.images:
        parser.error("--title 和 --images 为必填参数 (或使用 --login 扫码)")

    # 确保登录
    if not asyncio.run(ensure_login(account_file, headless=not args.headless)):
        print("❌ 登录失败，无法继续")
        sys.exit(1)

    # 发布
    result = asyncio.run(upload_note(
        account_file=account_file,
        title=args.title,
        note=args.note or "",
        image_paths=args.images,
        tags=args.tags,
        schedule_time=args.schedule,
        headless=args.headless,
        debug=args.debug,
    ))

    print()
    if result["success"]:
        print(f"=== 抖音发布成功 ===")
        print(f"标题: {result['title']}")
        print(f"图片: {result['images']} 张")
    else:
        print(f"❌ 发布失败: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
