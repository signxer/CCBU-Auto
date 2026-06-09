import asyncio, json, os
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    sp = os.path.join(OUT, "ccbu_session.json")
    if not os.path.exists(sp):
        print("No session"); return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(storage_state=sp, viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()

        url = "https://u.ccb.com/course/#/play/4437655b-1d1f-4ce1-9b89-532c2fb5ace6?workshopId=d8e40285-8484-41ce-97ad-6f169850cc24"
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        print(f"URL: {page.url}", flush=True)

        # ===== 1. Find ALL Aliplayer controls =====
        print("\n=== 1. Aliplayer control elements ===", flush=True)
        controls = await page.evaluate("""() => {
            const results = [];
            // Find all elements with class containing specific keywords
            const selectors = [
                '.prism-controlbar', '.prism-controlbar *',
                '.prism-rate', '.prism-rate *',
                '.rate-components', '.rate-components *',
                '[class*=\"rate\"]', '[class*=\"Rate\"]',
                '[class*=\"quality\"]', '[class*=\"Quality\"]',
                '.prism-quality', '.prism-quality *',
                '.quality-components', '.quality-components *',
                '[class*=\"speed\"]', '[class*=\"Speed\"]'
            ];
            selectors.forEach(sel => {
                try {
                    document.querySelectorAll(sel).forEach(el => {
                        const rect = el.getBoundingClientRect();
                        const t = (el.innerText || '').trim().slice(0, 40);
                        if (t || rect.width > 0) {
                            results.push({
                                sel: sel,
                                tag: el.tagName,
                                id: el.id || '',
                                cls: (el.className || '').slice(0, 80),
                                text: t,
                                visible: rect.width > 0 && rect.height > 0,
                                pos: {x: Math.round(rect.left), y: Math.round(rect.top), w: Math.round(rect.width), h: Math.round(rect.height)}
                            });
                        }
                    });
                } catch(e) {}
            });
            return results;
        }""")
        
        for c in controls:
            print(f"  [{c['sel'][:25]}] <{c['tag']}#{c['id'][:20]}> cls={c['cls'][:50]} vis={c['visible']} pos=({c['pos']['x']},{c['pos']['y']},{c['pos']['w']},{c['pos']['h']}) text='{c['text']}'", flush=True)

        # ===== 2. Find ALL rate list items =====
        print("\n=== 2. Rate list items ===", flush=True)
        rates = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('li.rate-list-li, [name=\"rate\"], .rate-list li, [class*=\"rate-list\"] li').forEach(el => {
                results.push({
                    tag: el.tagName,
                    cls: (el.className || '').slice(0,60),
                    text: (el.innerText || '').trim(),
                    visible: el.getBoundingClientRect().width > 0 && el.getBoundingClientRect().height > 0
                });
            });
            return results;
        }""")
        for r in rates:
            print(f"  <{r['tag']}> cls={r['cls'][:40]} text='{r['text']}' visible={r['visible']}", flush=True)

        if not rates:
            print("  (no rate items found - checking deeper)", flush=True)
            deeper = await page.evaluate("""() => {
                const all = document.querySelectorAll('*');
                const results = [];
                all.forEach(el => {
                    const t = (el.innerText || '').trim();
                    if (t && (t.endsWith('x') || t.endsWith('X')) && t.replace(/[\\d.xX]/g,'') === '') {
                        if (t.length <= 6) {
                            results.push({tag: el.tagName, cls: (el.className||'').slice(0,50), text: t});
                        }
                    }
                });
                return results.slice(0, 10);
            }""")
            for d in deeper:
                print(f"  [{d['tag']}] cls={d['cls'][:40]} text='{d['text']}'", flush=True)

        # ===== 3. Find quality elements =====
        print("\n=== 3. Quality elements ===", flush=True)
        qualities = await page.evaluate("""() => {
            const results = [];
            // Find elements displaying quality (like 1080P, 720P, etc.)
            const all = document.querySelectorAll('*');
            all.forEach(el => {
                const t = (el.innerText || '').trim();
                if (t && (t.endsWith('P') || t.endsWith('p')) && t.replace(/[\\dPp]/g,'') === '') {
                    if (t.length <= 8) {
                        results.push({tag: el.tagName, cls: (el.className||'').slice(0,50), text: t});
                    }
                }
                // Also check for quality components
                if (el.className && typeof el.className === 'string' && 
                    (el.className.includes('quality') || el.className.includes('Quality'))) {
                    const rt = (el.innerText || '').trim().slice(0, 60);
                    if (rt) results.push({tag: el.tagName, cls: el.className.slice(0,50), text: rt});
                }
            });
            return results;
        }""")
        for q in qualities:
            print(f"  [{q['tag']}] cls={q['cls'][:40]} text='{q['text']}'", flush=True)

        # ===== 4. Try clicking the rate button =====
        print("\n=== 4. Testing rate button click ===", flush=True)
        rate_btn = page.locator('.prism-rate').first
        rc = await rate_btn.count()
        print(f"prism-rate count: {rc}", flush=True)
        if rc > 0:
            vis = await rate_btn.is_visible()
            print(f"prism-rate visible: {vis}", flush=True)
            if vis:
                text = await rate_btn.inner_text()
                print(f"prism-rate text: {text.strip()}", flush=True)
                await rate_btn.click()
                await asyncio.sleep(2)
                # Check if rate list appeared
                rl = await page.locator('li.rate-list-li').count()
                print(f"rate-list-li after click: {rl}", flush=True)
                if rl > 0:
                    for ri in range(rl):
                        rt = await page.locator('li.rate-list-li').nth(ri).inner_text()
                        rv = await page.locator('li.rate-list-li').nth(ri).is_visible()
                        print(f"  [{ri}] text='{rt.strip()}' visible={rv}", flush=True)

        # ===== 5. Try clicking the quality button =====
        print("\n=== 5. Testing quality button click ===", flush=True)
        qbtn = page.locator('.quality-components, .prism-quality, [class*=quality]').first
        qc = await qbtn.count()
        print(f"quality button count: {qc}", flush=True)
        if qc > 0:
            qv = await qbtn.is_visible()
            print(f"quality button visible: {qv}", flush=True)
            if qv:
                qt = await qbtn.inner_text()
                print(f"quality button text: {qt.strip()[:40]}", flush=True)
                await qbtn.click()
                await asyncio.sleep(2)
                # Check quality options
                qlist = await page.locator('.quality-list li, [class*=quality] li').count()
                print(f"quality options after click: {qlist}", flush=True)
                if qlist > 0:
                    for qi in range(qlist):
                        qtxt = await page.locator('.quality-list li, [class*=quality] li').nth(qi).inner_text()
                        qv2 = await page.locator('.quality-list li, [class*=quality] li').nth(qi).is_visible()
                        print(f"  [{qi}] text='{qtxt.strip()}' visible={qv2}", flush=True)

        # ===== 6. Check page HTML for rate/quality structure =====
        print("\n=== 6. HTML structure around rate/quality ===", flush=True)
        html_sample = await page.evaluate("""() => {
            // Find the element that contains "1080P" and get its parent chain
            const all = document.querySelectorAll('*');
            let result = '';
            for (const el of all) {
                const t = (el.innerText || '').trim();
                if (t === '1080P' || t === '1.0x') {
                    result = el.outerHTML.slice(0, 300);
                    break;
                }
            }
            if (!result) {
                // Try to find any rate/quality text
                for (const el of all) {
                    const t = (el.innerText || '').trim();
                    if (t && (t.includes('x') || t.includes('P')) && t.length < 10) {
                        result = el.outerHTML.slice(0, 300);
                        break;
                    }
                }
            }
            return result || 'NOT FOUND';
        }""")
        print(f"HTML: {html_sample}", flush=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
