#!/usr/bin/env python3
"""Debug script: captures DOM structure for login detection, tag filtering, and workshop fetching."""
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

        # ========== 1. STUDY PAGE ==========
        log("\n===== 1. STUDY PAGE (login check) =====")
        await page.goto("https://u.ccb.com/portal/#/study", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        log(f"URL: {page.url}")
        log(f"Title: {await page.title()}")

        body_text = await page.locator("body").inner_text(timeout=5000)
        log(f"Body (first 800):\n{body_text[:800]}")

        with open(os.path.join(OUT, "debug_study.html"), "w", encoding="utf-8") as f:
            f.write(await page.content())

        # Input fields
        inputs = await page.evaluate("""() => 
            Array.from(document.querySelectorAll('input')).map(i => ({id:i.id, name:i.name, type:i.type, placeholder:i.placeholder, cls:i.className}))
        """)
        log(f"Inputs: {json.dumps(inputs, ensure_ascii=False, indent=2)}")

        buttons = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('button')).map(b => ({id:b.id, text:b.innerText.trim(), cls:b.className}))
        """)
        log(f"Buttons: {json.dumps(buttons, ensure_ascii=False, indent=2)}")

        # Login/user related elements
        login_els = await page.evaluate("""() => {
            const patterns = ['login','Login','user','User','avatar','Avatar','logout','Logout','登录','用户','头像','退出','个人'];
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const text = el.innerText.trim();
                const cls = el.className || '';
                if (text && text.length < 30 && patterns.some(p => text.includes(p))) {
                    results.push({tag: el.tagName, cls: cls.slice(0,80), text: text.slice(0,50)});
                }
            });
            return results.slice(0, 50);
        }""")
        log(f"Login-related elements: {json.dumps(login_els, ensure_ascii=False, indent=2)}")

        # Check if study page is loaded vs login page
        is_landing = await page.evaluate("""() => {
            const text = document.body.innerText;
            const hasLoginForm = !!document.querySelector('input[type="password"]');
            const hasLoginBtn = Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes('登录'));
            const hasStudyContent = text.includes('学习') && (text.includes('课程') || text.includes('专题') || text.includes('学时'));
            return { hasLoginForm, hasLoginBtn, hasStudyContent, textSample: text.slice(0,200) };
        }""")
        log(f"Login analysis: {json.dumps(is_landing, ensure_ascii=False, indent=2)}")

        # ========== 2. WORKSHOP INDEX ==========
        log("\n\n===== 2. WORKSHOP INDEX =====")
        await page.goto("https://u.ccb.com/workshop/#/index?collegeId=&departmentId=&orderby=praise",
                        wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        log(f"URL: {page.url}")
        ws_body = await page.locator("body").inner_text(timeout=5000)
        log(f"Body (first 800):\n{ws_body[:800]}")

        with open(os.path.join(OUT, "debug_workshop.html"), "w", encoding="utf-8") as f:
            f.write(await page.content())

        # All classes
        classes = await page.evaluate("""() => {
            const s = new Set();
            document.querySelectorAll('[class]').forEach(el => (el.className||'').split(/\\s+/).forEach(c => c && s.add(c)));
            return Array.from(s).sort();
        }""")
        log(f"Unique classes (first 150): {json.dumps(classes[:150], ensure_ascii=False)}")

        # Tag filter candidates
        filters = await page.evaluate("""() => {
            const keywords = ['教育','党性','理论','思想','专题','党建','政治','改革','发展','战略','建设'];
            const results = [];
            document.querySelectorAll('a, button, span, div, li, label').forEach(el => {
                const text = el.innerText.trim();
                if (text && text.length < 30 && keywords.some(k => text.includes(k))) {
                    const rect = el.getBoundingClientRect();
                    results.push({
                        tag: el.tagName, cls: (el.className||'').slice(0,80), text,
                        visible: rect.width > 0 && rect.height > 0,
                        rect: {w:Math.round(rect.width), h:Math.round(rect.height), t:Math.round(rect.top), l:Math.round(rect.left)}
                    });
                }
            });
            return results.slice(0, 80);
        }""")
        log(f"Tag filter candidates:\n{json.dumps(filters, ensure_ascii=False, indent=2)}")

        # Workshop cards
        cards = await page.evaluate("""() => {
            const selectors = ['[class*="card"]','[class*="Card"]','[class*="item"]','[class*="Item"]',
                               '[class*="list"]','[class*="List"]','li','[class*="workshop"]','[class*="Workshop"]'];
            const results = [];
            document.querySelectorAll(selectors.join(',')).forEach(el => {
                const text = el.innerText.trim();
                if (text && text.length > 15) {
                    const rect = el.getBoundingClientRect();
                    results.push({
                        tag: el.tagName, cls: (el.className||'').slice(0,80),
                        text: text.slice(0,200), childCount: el.children.length,
                        visible: rect.width > 0 && rect.height > 0,
                        rect: {w:Math.round(rect.width), h:Math.round(rect.height)}
                    });
                }
            });
            return results.slice(0, 50);
        }""")
        log(f"Workshop card candidates (visible, first 30):\n{json.dumps([c for c in cards if c['visible']][:30], ensure_ascii=False, indent=2)}")

        # ========== 3. WORKSHOP DETAIL ==========
        log("\n\n===== 3. WORKSHOP DETAIL =====")
        await page.goto("https://u.ccb.com/workshop/#/myworkshop/detail?id=76d439d4-671f-41e2-b713-6578204d7ccc",
                        wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        log(f"URL: {page.url}")
        det_body = await page.locator("body").inner_text(timeout=5000)
        log(f"Body (first 1000):\n{det_body[:1000]}")

        with open(os.path.join(OUT, "debug_detail.html"), "w", encoding="utf-8") as f:
            f.write(await page.content())

        # Buttons
        det_buttons = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('button, a')).filter(el => el.innerText.trim())
                .map(el => ({tag: el.tagName, text: el.innerText.trim().slice(0,80), cls: (el.className||'').slice(0,80)}))
        """)
        log(f"Buttons/links:\n{json.dumps(det_buttons, ensure_ascii=False, indent=2)}")

        # Course/chapter elements
        course_els = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[class*="course"],[class*="Course"],[class*="chapter"],[class*="Chapter"],[class*="lesson"],[class*="Lesson"],[class*="section"],[class*="Section"]').forEach(el => {
                const text = el.innerText.trim();
                if (text) results.push({tag: el.tagName, cls: (el.className||'').slice(0,80), text: text.slice(0,150)});
            });
            return results.slice(0, 40);
        }""")
        log(f"Course elements:\n{json.dumps(course_els, ensure_ascii=False, indent=2)}")

        log("\n\n===== DONE =====")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
