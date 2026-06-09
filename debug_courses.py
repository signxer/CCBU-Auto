#!/usr/bin/env python3
import asyncio, json, os, sys
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    # 加载凭证
    with open(os.path.join(OUT, "ccbu_credentials.json"), "r", encoding="utf-8") as f:
        creds = json.load(f)
    username = creds["username"]
    password = creds["password"]

    # 尝试加载已保存的session
    session_path = os.path.join(OUT, "ccbu_session.json")
    has_session = os.path.exists(session_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False,
            args=["--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"])
        
        if has_session:
            context = await browser.new_context(
                storage_state=session_path,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            print("使用已保存的会话", flush=True)
        else:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
        page = await context.new_page()

        # 如果没session，登录
        if not has_session:
            print("登录中...", flush=True)
            await page.goto("https://u.ccb.com/sys/#/login", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            await page.evaluate(f"""() => {{
                const el = document.querySelector('input[placeholder*="账号"]');
                if (el) {{
                    el.removeAttribute('maxlength');
                    el.removeAttribute('maxLength');
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    s.call(el, '{username}');
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }}""")
            await asyncio.sleep(0.5)
            
            await page.evaluate(f"""() => {{
                const el = document.getElementById('inputPwd');
                if (el) {{
                    el.removeAttribute('maxlength');
                    el.removeAttribute('maxLength');
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    s.call(el, '{password}');
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }}""")
            await asyncio.sleep(0.5)
            
            await page.get_by_role("button", name="登录").click()
            for i in range(30):
                await asyncio.sleep(1)
                if "/sys/#/login" not in page.url:
                    print("登录成功", flush=True)
                    break
            await context.storage_state(path=session_path)

        # ===== 导航到 myworkshop 详情页 =====
        target_id = "d8e40285-8484-41ce-97ad-6f169850cc24"
        url = f"https://u.ccb.com/workshop/#/myworkshop/detail?id={target_id}"
        print(f"\n导航到: {url}", flush=True)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(8)

        print(f"当前URL: {page.url}", flush=True)

        # 保存页面HTML
        html_path = os.path.join(OUT, "debug_myworkshop.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(await page.content())
        print(f"HTML已保存到: {html_path}", flush=True)

        # ===== 提取课程信息 =====
        print("\n=== 页面文本 ===", flush=True)
        body_text = await page.locator("body").inner_text(timeout=5000)
        print(body_text[:2000], flush=True)

        # 用 evaluate 提取课程结构
        print("\n=== 课程结构分析 ===", flush=True)
        course_info = await page.evaluate("""() => {
            const results = [];
            
            // 尝试找所有可能的课程/章节容器
            const selectors = [
                '[class*="chapter"]', '[class*="Chapter"]',
                '[class*="section"]', '[class*="Section"]',
                '[class*="lesson"]', '[class*="Lesson"]',
                '[class*="course"]', '[class*="Course"]',
                '[class*="list"]', '[class*="content"]'
            ];
            
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    const text = el.innerText.trim();
                    if (text && text.length > 5 && text.length < 500) {
                        const rect = el.getBoundingClientRect();
                        results.push({
                            selector: sel,
                            tag: el.tagName,
                            class: (el.className || '').slice(0,100),
                            text: text.slice(0, 200),
                            visible: rect.width > 0 && rect.height > 0,
                            rect: {w: Math.round(rect.width), h: Math.round(rect.height)}
                        });
                    }
                });
            });
            return results.slice(0, 50);
        }""")
        
        print(f"\n找到 {len(course_info)} 个课程相关元素:", flush=True)
        for c in course_info:
            print(f"  [{c['tag']}] class='{c['class'][:60]}'", flush=True)
            print(f"     text: {c['text'][:150]}", flush=True)
            print(f"     visible={c['visible']} rect={c['rect']}", flush=True)
            print()

        # 查找所有链接
        print("\n=== 所有链接 ===", flush=True)
        all_links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.getAttribute('href') || '',
                text: a.innerText.trim().slice(0, 80),
                class: (a.className || '').slice(0, 40)
            })).filter(a => a.text || a.href);
        }""")
        for link in all_links:
            print(f"  href='{link['href'][:80]}' text='{link['text']}' class='{link['class']}'", flush=True)

        # 查找按钮
        print("\n=== 所有按钮 ===", flush=True)
        all_buttons = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.innerText.trim().slice(0, 60),
                class: (b.className || '').slice(0, 40)
            })).filter(b => b.text);
        }""")
        for btn in all_buttons:
            print(f"  text='{btn['text']}' class='{btn['class']}'", flush=True)

        # 查找进度相关元素
        print("\n=== 进度元素 ===", flush=True)
        progress_els = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[class*="progress"], [class*="Progress"], [class*="rate"], [class*="Rate"], [class*="percent"]').forEach(el => {
                results.push({
                    tag: el.tagName,
                    class: (el.className || '').slice(0, 60),
                    text: el.innerText.trim().slice(0, 100)
                });
            });
            return results;
        }""")
        for p in progress_els:
            print(f"  [{p['tag']}] class='{p['class']}' text='{p['text']}'", flush=True)

        # 尝试获取更结构化的课程信息
        print("\n=== 尝试结构化提取 ===", flush=True)
        structured = await page.evaluate("""() => {
            // 尝试找到课程列表容器
            // 常见模式：包含"立即学习"按钮的父容器
            const results = [];
            
            // 找所有包含课程进度或名称的区域
            const items = document.querySelectorAll('[class*="item"], [class*="Item"], li, [class*="row"], [class*="Row"]');
            items.forEach(el => {
                const text = el.innerText.trim();
                // 找包含课程特征的项
                if (text && (text.includes('立即学习') || text.includes('继续学习') || 
                    text.includes('已学习') || text.includes('进度') || text.includes('学时'))) {
                    results.push({
                        tag: el.tagName,
                        class: (el.className || '').slice(0, 60),
                        text: text.slice(0, 300)
                    });
                }
            });
            return results.slice(0, 30);
        }""")
        for s in structured:
            print(f"  [{s['tag']}] class='{s['class']}'", flush=True)
            print(f"     text: {s['text']}", flush=True)
            print()

        await browser.close()
        print("\n=== 完成 ===", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
