import asyncio, json, os
from playwright.async_api import async_playwright

async def main():
    sp = "/Users/livrestrela/Documents/CCBU-Auto/ccbu_session.json"
    if not os.path.exists(sp):
        print("No session"); return
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False)
        c = await b.new_context(storage_state=sp, viewport={"width": 1920, "height": 1080})
        page = await c.new_page()
        await page.goto("https://u.ccb.com/course/#/list/1", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)
        print(f"URL: {page.url}")
        body = await page.locator("body").inner_text()
        print(f"\n页面文本 (前1000):\n{body[:1000]}")

        # 检查表格行
        rows = page.locator("table.courseTable tr, .courseTable tr, tr")
        cnt = await rows.count()
        print(f"\ntr 总数: {cnt}")
        for i in range(min(cnt, 30)):
            tds = rows.nth(i).locator("td")
            tdc = await tds.count()
            if tdc >= 2:
                first = (await tds.nth(0).inner_text()).strip()
                # Check if it looks like data (not header)
                if '类型' not in first and len(first) < 15:
                    second = (await tds.nth(1).inner_text()).strip()[:40]
                    action = ""
                    try:
                        btn = rows.nth(i).locator("a, button, span.btn, [class*=btn]").first
                        action = (await btn.inner_text()).strip() if await btn.count() > 0 else ""
                    except:
                        pass
                    print(f"  [{i}] tds={tdc} type='{first}' title='{second}' btn='{action[:20]}'")
        
        # 检查特定选择器
        for sel in ["table tr", ".courseTable tr", "[class*=course] tr", "tr.text-center"]:
            c2 = await page.locator(sel).count()
            print(f"  selector '{sel}': {c2}")

        # 保存HTML
        with open("/Users/livrestrela/Documents/CCBU-Auto/debug_courselist.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
        print("\nHTML saved")

        await b.close()
asyncio.run(main())
