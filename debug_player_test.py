import asyncio, json, os
from playwright.async_api import async_playwright

async def main():
    sp = "/Users/livrestrela/Documents/CCBU-Auto/ccbu_session.json"
    if not os.path.exists(sp):
        print("No session file!"); return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(storage_state=sp, viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()

        url = "https://u.ccb.com/course/#/play/5484b66e-84fe-4626-8a42-e4a194949cc9?workshopId=d8e40285-8484-41ce-97ad-6f169850cc24"
        print(f"1. 打开视频: {url}", flush=True)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(10)

        # ===== 点击播放器让控制栏浮现 =====
        print("\n2. hover播放器显示控制栏", flush=True)
        player = page.locator(".prism-player, video, #player_area")
        if await player.count() > 0:
            await player.first.click()
            await asyncio.sleep(2)
            # Click again to make sure video is playing (might need to click play button)
            play_btn = page.locator(".prism-big-play-btn, .prism-play-btn")
            if await play_btn.count() > 0 and await play_btn.first.is_visible():
                await play_btn.first.click()
                await asyncio.sleep(2)

        # ===== 倍速切换测试 =====
        print("\n=== 测试: 2倍速度 ===", flush=True)
        rate_btn = page.locator(".current-rate").first
        rc = await rate_btn.count()
        print(f"  倍速按钮数量: {rc}", flush=True)
        if rc > 0:
            rv = await rate_btn.is_visible()
            print(f"  倍速按钮可见: {rv}", flush=True)
            rt = (await rate_btn.inner_text()).strip()
            print(f"  当前倍速: {rt}", flush=True)
            
            await rate_btn.click(force=True)
            await asyncio.sleep(2)
            
            opt = page.locator('li[data-rate="2.0"]').first
            oc = await opt.count()
            print(f"  2.0x选项数量: {oc}", flush=True)
            if oc > 0:
                ot = (await opt.inner_text()).strip()
                print(f"  点击: {ot}", flush=True)
                await opt.click(force=True)
                await asyncio.sleep(2)
                new_rt = (await rate_btn.inner_text()).strip()
                print(f"  切换后显示: {new_rt}", flush=True)
                if "2" in new_rt:
                    print("  ✅ 2倍速度成功!", flush=True)
                else:
                    print("  ❌ 2倍速度失败!", flush=True)
            else:
                print("  ❌ 未找到2.0x选项", flush=True)
        else:
            print("  ❌ 未找到倍速按钮", flush=True)

        # ===== 画质切换测试 =====
        print("\n=== 测试: 最低画质 ===", flush=True)
        qbtn = page.locator(".current-quality").first
        qc = await qbtn.count()
        print(f"  画质按钮数量: {qc}", flush=True)
        if qc > 0:
            qv = await qbtn.is_visible()
            print(f"  画质按钮可见: {qv}", flush=True)
            qt = (await qbtn.inner_text()).strip()
            print(f"  当前画质: {qt}", flush=True)
            
            await qbtn.click(force=True)
            await asyncio.sleep(2)
            
            items = page.locator(".quality-list li")
            ic = await items.count()
            print(f"  画质选项数: {ic}", flush=True)
            if ic > 0:
                for i in range(ic):
                    t = (await items.nth(i).inner_text()).strip()
                    print(f"    [{i}] {t}", flush=True)
                lowest = items.nth(ic - 1)
                lt = (await lowest.inner_text()).strip()
                print(f"  选择最低: {lt}", flush=True)
                await lowest.click(force=True)
                await asyncio.sleep(2)
                new_qt = (await qbtn.inner_text()).strip()
                print(f"  切换后显示: {new_qt}", flush=True)
                if lt in new_qt:
                    print("  ✅ 最低画质成功!", flush=True)
                else:
                    print(f"  ⚠️ 可能已切换 (当前显示: {new_qt})", flush=True)
            else:
                print("  ❌ 未找到画质选项", flush=True)
        else:
            print("  ❌ 未找到画质按钮", flush=True)

        # ===== 最终状态 =====
        print("\n=== 最终状态 ===", flush=True)
        try:
            final_rate = (await page.locator(".current-rate").first.inner_text()).strip()
            print(f"  倍速: {final_rate}", flush=True)
        except:
            print("  倍速: 读取失败", flush=True)
        try:
            final_qual = (await page.locator(".current-quality").first.inner_text()).strip()
            print(f"  画质: {final_qual}", flush=True)
        except:
            print("  画质: 读取失败", flush=True)

        print("\n=== 测试完成! 浏览器保持打开供查看 ===", flush=True)
        print("按回车键关闭浏览器...", flush=True)
        input()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
