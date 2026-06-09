#!/usr/bin/env python3
import asyncio, json, os
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    session_path = os.path.join(OUT, "ccbu_session.json")
    if not os.path.exists(session_path):
        print("No session file - please run main.py first to login", flush=True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=session_path,
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        # Navigate to myworkshop detail
        ws_id = "d8e40285-8484-41ce-97ad-6f169850cc24"
        await page.goto(f"https://u.ccb.com/workshop/#/myworkshop/detail?id={ws_id}",
                        wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)
        await page.wait_for_selector("tr.text-center", timeout=15000)
        await asyncio.sleep(3)

        print(f"URL: {page.url}", flush=True)

        # ===== 提取所有课程信息 + 可能的内嵌链接 =====
        info = await page.evaluate("""() => {
            const rows = document.querySelectorAll('tr.text-center');
            const results = [];
            rows.forEach((row, idx) => {
                const cells = row.querySelectorAll('td');
                if (cells.length < 6) return;
                
                // 标题
                const title = cells[1] ? cells[1].innerText.trim() : '';
                
                // 操作列
                const actionCell = cells[5];
                const actionText = actionCell ? actionCell.innerText.trim() : '';
                
                // 寻找操作列里所有的链接/有href的父级
                const links = actionCell ? actionCell.querySelectorAll('a, [href]') : [];
                const hrefs = [];
                links.forEach(a => {
                    const h = a.getAttribute('href');
                    if (h) hrefs.push(h);
                });
                
                // 看行的data属性
                const rowAttrs = {};
                for (const attr of row.attributes) {
                    rowAttrs[attr.name] = attr.value;
                }
                
                results.push({
                    index: idx,
                    title: title.slice(0, 80),
                    action: actionText,
                    hrefs: hrefs,
                    rowAttrs: rowAttrs
                });
            });
            return results;
        }""")

        print(f"\n=== 课程行数据 ({len(info)} 行) ===", flush=True)
        for row in info:
            print(f"\nRow {row['index']}: {row['title']}", flush=True)
            print(f"  Action: {row['action']}", flush=True)
            print(f"  Hrefs: {row['hrefs']}", flush=True)
            print(f"  Row attrs: {json.dumps(row['rowAttrs'], ensure_ascii=False)}", flush=True)

        # ===== 尝试找到每个edit-block的真实链接 =====
        print("\n\n=== edit-block 元素详情 ===", flush=True)
        edit_blocks = await page.evaluate("""() => {
            const blocks = document.querySelectorAll('.edit-block');
            const results = [];
            blocks.forEach(el => {
                const info = {
                    text: el.innerText.trim(),
                    tag: el.tagName,
                    class: el.className,
                    outerHTML: el.outerHTML.slice(0, 300)
                };
                // Check all parent attributes
                let parent = el.parentElement;
                let level = 0;
                while (parent && level < 5) {
                    const pAttrs = {};
                    for (const attr of parent.attributes) {
                        pAttrs[attr.name] = attr.value;
                    }
                    info[`parent_l${level}`] = {
                        tag: parent.tagName,
                        attrs: pAttrs,
                        text: parent.innerText.trim().slice(0, 60)
                    };
                    parent = parent.parentElement;
                    level++;
                }
                results.push(info);
            });
            return results.slice(0, 3);
        }""")
        
        for b in edit_blocks:
            print(f"\nBlock: {json.dumps(b, ensure_ascii=False, indent=2)}", flush=True)

        # ===== 检查页面上是否有隐藏的课程列表数据 =====
        print("\n\n=== 检查页面JavaScript中的课程数据 ===", flush=True)
        js_data = await page.evaluate("""() => {
            // 检查window上有没有课程数据
            const keys = Object.keys(window).filter(k => 
                k.toLowerCase().includes('course') || 
                k.toLowerCase().includes('lesson') || 
                k.toLowerCase().includes('curricul') ||
                k.toLowerCase().includes('workshop') ||
                k.toLowerCase().includes('viii')
            );
            return keys.slice(0, 20);
        }""")
        print(f"Window keys with course/lesson: {js_data}", flush=True)

        # ===== 尝试通过Vue组件获取数据 =====
        print("\n\n=== Vue组件数据 ===", flush=True)
        vue_data = await page.evaluate("""() => {
            const results = {};
            // 找 __vue__ 属性
            const appEl = document.querySelector('#app, [data-v-1668e4c0]');
            if (appEl && appEl.__vue__) {
                results.hasVue = true;
                // Try to find component data
                const keys = Object.keys(appEl.__vue__);
                results.vueKeys = keys.slice(0, 10);
            }
            // Check for __vue_app__
            if (window.__vue_app__) {
                results.hasVueApp = true;
            }
            // Check for Vue on any DOM elements
            const firstRow = document.querySelector('tr.text-center');
            if (firstRow) {
                const vKeys = Object.keys(firstRow).filter(k => k.startsWith('__vue'));
                results.rowVueKeys = vKeys;
            }
            return results;
        }""")
        print(f"Vue data: {json.dumps(vue_data, ensure_ascii=False, indent=2)}", flush=True)

        # ===== 尝试：点击"立即学习"并拦截请求 =====
        print("\n\n=== 拦截网络请求获取课程URL ===", flush=True)
        captured_urls = []
        
        async def on_request(request):
            url = request.url
            if '/course/' in url or '/lesson/' in url or '/detail' in url:
                if url != page.url:
                    captured_urls.append(url)
        
        page.on("request", on_request)
        
        # 点击第一个"立即学习"
        first_btn = page.locator("span.edit-block").first
        await first_btn.click()
        await asyncio.sleep(5)
        
        page.remove_listener("request", on_request)
        
        print(f"捕获的请求URLs: {json.dumps(captured_urls, ensure_ascii=False, indent=2)}", flush=True)
        print(f"当前URL: {page.url}", flush=True)

        # Check for new pages
        if len(context.pages) > 1:
            new_page = context.pages[-1]
            await new_page.bring_to_front()
            await new_page.wait_for_timeout(3000)
            print(f"\n新标签页URL: {new_page.url}", flush=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
