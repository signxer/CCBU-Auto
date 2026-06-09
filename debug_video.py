import asyncio, json, os
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    session_path = os.path.join(OUT, "ccbu_session.json")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=session_path,
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        url = "https://u.ccb.com/course/#/play/aab700fd-6eef-4fa0-a98a-732d3c675cfc?workshopId=d8e40285-8484-41ce-97ad-6f169850cc24"
        print(f"Navigating to: {url}", flush=True)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        print(f"URL: {page.url}", flush=True)
        page_text = await page.locator("body").inner_text(timeout=5000)
        print(f"\n=== 页面文本 (前1000字) ===\n{page_text[:1000]}", flush=True)

        # 保存HTML
        with open(os.path.join(OUT, "debug_video.html"), "w", encoding="utf-8") as f:
            f.write(await page.content())
        print("\nHTML saved to debug_video.html", flush=True)

        # 查找所有显示百分比的元素
        print("\n=== 进度/百分比元素 ===", flush=True)
        pct_els = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const t = el.innerText || '';
                if (t.includes('%')) {
                    results.push({
                        tag: el.tagName,
                        id: el.id || '',
                        cls: (el.className || '').slice(0,80),
                        text: t.trim().slice(0, 100),
                        rect: el.getBoundingClientRect()
                    });
                }
            });
            return results.slice(0, 30);
        }""")
        for el in pct_els:
            print(f"  [{el['tag']}#{el['id']}] class='{el['cls']}' rect={el['rect']}", flush=True)
            print(f"    text: {el['text']}", flush=True)

        # 查找视频元素及其属性
        print("\n=== 视频元素 ===", flush=True)
        video_info = await page.evaluate("""() => {
            const v = document.querySelector('video');
            if (!v) return { found: false, msg: 'No video element' };
            return {
                found: true,
                duration: v.duration,
                currentTime: v.currentTime,
                paused: v.paused,
                readyState: v.readyState,
                src: (v.src || '').slice(0, 100),
                rect: v.getBoundingClientRect()
            };
        }""")
        print(json.dumps(video_info, indent=2, ensure_ascii=False), flush=True)

        # 找所有按钮
        print("\n=== 所有按钮 ===", flush=True)
        btns = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).map(b => ({
                text: (b.innerText || '').trim().slice(0, 40),
                cls: (b.className || '').slice(0, 50)
            })).filter(b => b.text);
        }""")
        for b in btns:
            print(f"  button: '{b['text']}' class='{b['cls']}'", flush=True)

        # 查找Aliplayer相关元素
        print("\n=== Aliplayer 相关元素 ===", flush=True)
        ali_els = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[class*="ali"], [class*="prism"], [id*="ali"], [class*="player"], [class*="Player"]').forEach(el => {
                results.push({
                    tag: el.tagName,
                    id: el.id || '',
                    cls: (el.className || '').slice(0, 80),
                    text: (el.innerText || '').trim().slice(0, 50)
                });
            });
            return results.slice(0, 20);
        }""")
        for el in ali_els:
            print(f"  [{el['tag']}#{el['id']}] class='{el['cls']}' text='{el['text']}'", flush=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
