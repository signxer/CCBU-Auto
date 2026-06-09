#!/usr/bin/env python3
import asyncio, json, os
from playwright.async_api import async_playwright

STORAGE = "/Users/livrestrela/Documents/CCBU-Auto/ccbu_session.json"
OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=STORAGE,
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        def log(msg):
            print(msg, flush=True)

        # ===== WORKSHOP INDEX =====
        log("=== 1. WORKSHOP INDEX ===")
        await page.goto("https://u.ccb.com/workshop/#/index?collegeId=&departmentId=&orderby=praise",
                        wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        log(f"URL: {page.url}")
        log(f"Title: {await page.title()}")

        body = await page.locator("body").inner_text(timeout=5000)
        log(f"Body (first 800):\n{body[:800]}")

        with open(os.path.join(OUT, "debug_loggedin.html"), "w", encoding="utf-8") as f:
            f.write(await page.content())

        # All classes
        classes = await page.evaluate("""() => {
            const s = new Set();
            document.querySelectorAll('[class]').forEach(el => (el.className||'').split(/\\s+/).forEach(c => c && s.add(c)));
            return Array.from(s).sort();
        }""")
        log(f"Unique classes (first 80): {json.dumps(classes[:80], ensure_ascii=False)}")

        # ALL li elements with their classes and text preview
        all_lis = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('li').forEach(el => {
                const text = el.innerText.trim().slice(0, 80);
                results.push({tag:el.tagName, cls:(el.className||'').slice(0,60), text});
            });
            return results.slice(0, 60);
        }""")
        log(f"All <li> elements:\n{json.dumps(all_lis, ensure_ascii=False, indent=2)}")

        # ALL div elements with certain class patterns
        pattern_divs = await page.evaluate("""() => {
            const keywords = ['card','Card','item','Item','list','List','workshop','Workshop','content','title','tag','sort'];
            const results = [];
            document.querySelectorAll('div[class]').forEach(el => {
                const cls = el.className || '';
                if (keywords.some(k => cls.includes(k))) {
                    const text = el.innerText.trim().slice(0, 100);
                    results.push({cls: cls.slice(0,80), text, childCount: el.children.length});
                }
            });
            return results.slice(0, 40);
        }""")
        log(f"Pattern divs:\n{json.dumps(pattern_divs, ensure_ascii=False, indent=2)}")

        # Tag filter structure
        filters = await page.evaluate("""() => {
            const results = [];
            // Look for tag-related containers
            const containers = document.querySelectorAll('[class*="sort"], [class*="filter"], [class*="tag"], [class*="Tag"]');
            containers.forEach(el => {
                results.push({tag:el.tagName, cls:(el.className||'').slice(0,80), text:el.innerText.trim().slice(0,150)});
            });
            return results;
        }""")
        log(f"Filter/sort/tag containers:\n{json.dumps(filters, ensure_ascii=False, indent=2)}")

        # Try to find workshop items with various selectors
        for sel in ['li', 'div[class*="card"]', 'div[class*="Card"]', 'div[class*="list"]', 'div[class*="item"]',
                    'div[class*="workshop"]', 'div[class*="content"]', 'a', 'ul > li', 'li[class]']:
            try:
                cnt = await page.locator(sel).count()
                if cnt > 0:
                    log(f"  Selector '{sel}': {cnt} elements")
            except:
                pass

        # Find H2/H3/H4 elements to see section headers
        headers = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('h2,h3,h4')).map(h => ({tag:h.tagName, text:h.innerText.trim().slice(0,80)}));
        }""")
        log(f"Headers:\n{json.dumps(headers, ensure_ascii=False, indent=2)}")

        # Check pagination
        pagination = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[class*="page"], [class*="Page"], [class*="pagi"]').forEach(el => {
                results.push({tag:el.tagName, cls:(el.className||'').slice(0,80), text:el.innerText.trim().slice(0,100)});
            });
            return results;
        }""")
        log(f"Pagination elements:\n{json.dumps(pagination, ensure_ascii=False, indent=2)}")

        log("\n=== DONE ===")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
