import asyncio, json, os
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    session_path = os.path.join(OUT, "ccbu_session.json")
    if not os.path.exists(session_path):
        print("No session file", flush=True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=session_path, viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        url = "https://u.ccb.com/workshop/#/myworkshop/detail?id=77f1842b-6e73-4c12-8817-767a51a67901"
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        body = await page.locator("body").inner_text()
        print(f"页面文本前500字:\n{body[:500]}", flush=True)

        # 获取课程表格
        rows = page.locator("tr.text-center")
        cnt = await rows.count()
        print(f"\n共 {cnt} 行课程/图书", flush=True)
        for i in range(cnt):
            type_el = rows.nth(i).locator("td:nth-child(1)")
            title_el = rows.nth(i).locator("td:nth-child(2)")
            action_el = rows.nth(i).locator("span.edit-block")
            ctype = await type_el.inner_text()
            title = await title_el.inner_text()
            action = await action_el.inner_text() if await action_el.count() > 0 else "无操作"
            print(f"  [{i}] type='{ctype.strip()}' title='{title.strip()[:50]}' action='{action.strip()}'", flush=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
