#!/usr/bin/env python3
import asyncio, json, os
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    with open(os.path.join(OUT, "ccbu_credentials.json"), "r", encoding="utf-8") as f:
        creds = json.load(f)
    username = creds["username"]
    password = creds["password"]
    print(f"Using credentials: {username} / {'*' * len(password)}", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # ===== LOGIN =====
        print("\n=== LOGIN ===", flush=True)
        await page.goto("https://u.ccb.com/sys/#/login", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Set username
        await page.evaluate(f"""() => {{
            const el = document.querySelector('input[placeholder*="账号"]');
            if (el) {{
                el.removeAttribute('maxlength');
                el.removeAttribute('maxLength');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, '{username}');
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""")
        await asyncio.sleep(0.5)

        # Verify username
        actual_uname = await page.evaluate("""() => {
            const el = document.querySelector('input[placeholder*="账号"]');
            return el ? el.value : '';
        }""")
        print(f"  Username field: [{actual_uname}] ({len(actual_uname)}/{len(username)} chars)", flush=True)

        if len(actual_uname) < len(username):
            print("  Username truncated, using keyboard fallback...", flush=True)
            ui = page.locator('input[placeholder*="账号"]')
            await ui.click()
            await page.keyboard.press("Meta+a")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.3)
            await page.keyboard.type(username, delay=150)
            actual_uname = await page.evaluate("""() => {
                const el = document.querySelector('input[placeholder*="账号"]');
                return el ? el.value : '';
            }""")
            print(f"  After keyboard: [{actual_uname}]", flush=True)

        # Set password
        await page.evaluate(f"""() => {{
            const el = document.getElementById('inputPwd');
            if (el) {{
                el.removeAttribute('maxlength');
                el.removeAttribute('maxLength');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, '{password}');
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""")
        await asyncio.sleep(0.5)

        # Click login
        login_btn = page.get_by_role("button", name="登录")
        await login_btn.click()

        # Wait for redirect
        for i in range(30):
            await asyncio.sleep(1)
            url = page.url
            if "/sys/#/login" not in url:
                print(f"  Login succeeded, redirected to: {url}", flush=True)
                break
        else:
            print("  Login did not redirect, checking for errors...", flush=True)
            body = await page.locator("body").inner_text()
            print(f"  Page text: {body[:300]}", flush=True)

        # Navigate to study page to verify
        await page.goto("https://u.ccb.com/portal/#/study", wait_until="networkidle", timeout=15000)
        await asyncio.sleep(3)
        url = page.url
        print(f"Study page URL: {url}", flush=True)
        notlogin = await page.locator(".cuWeb-swipe-web-info-notlogin-tips").count()
        print(f"Not-login tips visible: {notlogin}", flush=True)

        # Save session
        await context.storage_state(path=os.path.join(OUT, "ccbu_session.json"))
        print("Session saved to ccbu_session.json", flush=True)

        # ===== WORKSHOP PAGE =====
        print("\n=== WORKSHOP PAGE ===", flush=True)
        await page.goto("https://u.ccb.com/workshop/#/index?collegeId=&departmentId=&orderby=praise",
                        wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        print(f"URL: {page.url}", flush=True)

        with open(os.path.join(OUT, "debug_loggedin.html"), "w", encoding="utf-8") as f:
            f.write(await page.content())
        print("HTML saved to debug_loggedin.html", flush=True)

        # ===== TAG FILTERS DEBUG =====
        print("\n--- TAG FILTERS ---", flush=True)

        # Check tag-tree-list
        tag_list = await page.locator("ul.tag-tree-list").count()
        print(f"ul.tag-tree-list found: {tag_list}", flush=True)

        if tag_list > 0:
            # Count span.single-tag inside tag-tree-list
            all_span_tags = page.locator("ul.tag-tree-list span.single-tag")
            cnt = await all_span_tags.count()
            print(f"ul.tag-tree-list span.single-tag count: {cnt}", flush=True)
            for i in range(cnt):
                text = (await all_span_tags.nth(i).inner_text()).strip()
                visible = await all_span_tags.nth(i).is_visible()
                print(f"  [{i}] text='{text}' visible={visible}", flush=True)

            # Count div.tag-second.single-tag (the "不限" buttons)
            all_div_tags = page.locator("ul.tag-tree-list div.tag-second.single-tag")
            cnt2 = await all_div_tags.count()
            print(f"ul.tag-tree-list div.tag-second.single-tag count: {cnt2}", flush=True)
            for i in range(cnt2):
                text = (await all_div_tags.nth(i).inner_text()).strip()
                visible = await all_div_tags.nth(i).is_visible()
                print(f"  [{i}] text='{text}' visible={visible}", flush=True)

            # Try full structure dump
            filter_html = await page.evaluate("""() => {
                const el = document.querySelector('ul.tag-tree-list');
                return el ? el.innerHTML.slice(0, 3000) : 'NOT FOUND';
            }""")
            print(f"\nFilter innerHTML (first 3000 chars):\n{filter_html}", flush=True)
        else:
            print("tag-tree-list NOT found. Looking for filters another way...", flush=True)

            # Try workshop-sort-wrap
            sort_wrap = await page.locator(".workshop-sort-wrap").count()
            print(f"workshop-sort-wrap count: {sort_wrap}", flush=True)

            # Search for any element containing the tag text
            for tag in ["党性教育", "党的创新理论教育和党性教育"]:
                candidates = page.locator("span, div, li").filter(has_text=tag)
                cc = await candidates.count()
                print(f"  Elements containing '{tag}': {cc}", flush=True)
                for j in range(min(cc, 10)):
                    t = (await candidates.nth(j).inner_text()).strip()
                    cls = await candidates.nth(j).get_attribute("class") or ""
                    vid = await candidates.nth(j).is_visible()
                    print(f"    [{j}] text='{t}' visible={vid} class='{cls[:60]}'", flush=True)

        # ===== WORKSHOP CARDS DEBUG =====
        print("\n--- WORKSHOP CARDS ---", flush=True)

        # Test different selectors
        for sel, desc in [
            (".workshop-content-list li.clearfix", "li.clearfix in .workshop-content-list"),
            (".workshop-content-list > ul > li", ".workshop-content-list > ul > li"),
            (".workshop-content-list li", "any li in .workshop-content-list"),
            ("li.clearfix", "all li.clearfix"),
            ("[class*=clearfix]", "[class*=clearfix]"),
        ]:
            cnt = await page.locator(sel).count()
            print(f"  {desc}: {cnt}", flush=True)

        # Get first few workshop card texts
        cards = await page.locator(".workshop-content-list li.clearfix").all()
        for i, card in enumerate(cards[:3]):
            title = await card.locator(".workshop-list-content-title").inner_text(timeout=3000)
            print(f"  Card {i}: title='{title.strip()[:60]}'", flush=True)
            # Get detail link
            link = card.locator("a").first
            href = await link.get_attribute("href") or ""
            print(f"    link href='{href}'", flush=True)

        # ===== PAGINATION =====
        print("\n--- PAGINATION ---", flush=True)
        page_els = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[class*=\"page\"], [class*=\"Page\"], [class*=\"pagi\"], .el-pagination, .pagination').forEach(el => {
                results.push({tag: el.tagName, cls: (el.className || '').slice(0, 80), text: el.innerText.trim().slice(0, 150)});
            });
            return results;
        }""")
        print(f"Pagination elements:\n{json.dumps(page_els, ensure_ascii=False, indent=2)}", flush=True)

        # Try clicking "党性教育" > "党的创新理论教育和党性教育" 
        print("\n--- TRYING FILTER CLICK ---", flush=True)
        tag_spans = page.locator("ul.tag-tree-list span.single-tag")
        cnt = await tag_spans.count()
        print(f"span.single-tag count: {cnt}", flush=True)
        for i in range(cnt):
            text = (await tag_spans.nth(i).inner_text()).strip()
            if text == "党的创新理论教育和党性教育":
                print(f"Found target tag at index {i}, clicking...", flush=True)
                await tag_spans.nth(i).click()
                await page.wait_for_timeout(5000)
                print("Clicked! Checking page state...", flush=True)
                break

        await asyncio.sleep(3)
        print(f"After filter URL: {page.url}", flush=True)
        body2 = await page.locator("body").inner_text(timeout=3000)
        print(f"Page body (first 500):\n{body2[:500]}", flush=True)

        await browser.close()
        print("\n=== DONE ===", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
