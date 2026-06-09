import asyncio, os, json
from playwright.async_api import async_playwright

async def main():
    sp = "/Users/livrestrela/Documents/CCBU-Auto/ccbu_session.json"
    if not os.path.exists(sp):
        print("No session"); return
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False)
        c = await b.new_context(storage_state=sp, viewport={"width": 1920, "height": 1080})
        page = await c.new_page()
        await page.goto("https://u.ccb.com/portal/#/studyCenter", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)
        print(f"URL: {page.url}")

        body = await page.locator("body").inner_text()
        print(f"\n页面文本:\n{body[:2000]}")

        # 查找学时相关元素
        hours_info = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const t = el.innerText.trim();
                if (t && (t.includes('学时') || t.includes('培训'))) {
                    if (t.length < 60) {
                        results.push({
                            tag: el.tagName,
                            cls: (el.className || '').slice(0,50),
                            text: t
                        });
                    }
                }
            });
            return results.filter(r => r.text);
        }""")
        print("\n学时相关元素:")
        for h in hours_info:
            print(f"  [{h['tag']}] cls={h['cls'][:40]} text='{h['text']}'")

        # 保存HTML
        with open("/Users/livrestrela/Documents/CCBU-Auto/debug_studycenter.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
        print("\nHTML saved")

        await b.close()
asyncio.run(main())
