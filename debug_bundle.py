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

        ws_id = "400bc634-9b14-420a-a472-b1a14dd89efe"
        url = f"https://u.ccb.com/workshop/#/myworkshop/detail?id={ws_id}"
        print(f"1. 导航到专题班: {url}", flush=True)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        # 获取课程列表
        print(f"\n2. 当前URL: {page.url}", flush=True)
        body = await page.locator("body").inner_text(timeout=5000)
        print(f"\n3. 页面文本前800字:\n{body[:800]}", flush=True)

        # 检查课程表格
        print("\n4. 课程表格行:", flush=True)
        rows = page.locator("tr.text-center")
        cnt = await rows.count()
        print(f"   共 {cnt} 行", flush=True)

        for i in range(min(cnt, 5)):
            action = await rows.nth(i).locator("span.edit-block").inner_text()
            title = await rows.nth(i).locator("td:nth-child(2)").inner_text()
            print(f"   [{i}] action={action.strip()} title={title.strip()[:60]}", flush=True)

        # 点第一个课程，看弹窗
        print("\n5. 点击第一个课程...", flush=True)
        first_btn = rows.nth(0).locator("span.edit-block").first
        async with page.expect_event("popup", timeout=20000) as pi:
            await first_btn.click()

        popup = await pi.value
        await popup.wait_for_load_state()
        await asyncio.sleep(5)
        print(f"   弹窗URL: {popup.url}", flush=True)

        # 保存弹窗HTML
        html = await popup.content()
        with open(os.path.join(OUT, "debug_bundle_popup.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print("   HTML已保存到 debug_bundle_popup.html", flush=True)

        # 分析弹窗页面结构
        popup_text = await popup.locator("body").inner_text()
        print(f"\n6. 弹窗页面文本:\n{popup_text[:1500]}", flush=True)

        # 查找课程/章节列表
        print("\n7. 查找课程相关元素:", flush=True)
        info = await popup.evaluate("""() => {
            const results = [];
            const classes = ['chapter', 'Chapter', 'section', 'Section', 'lesson', 'Lesson', 
                           'course', 'Course', 'list', 'List', 'item', 'Item', 'playlist'];
            classes.forEach(cls => {
                document.querySelectorAll('[class*=\"' + cls + '\"]').forEach(el => {
                    const t = el.innerText.trim();
                    if (t && t.length > 3 && t.length < 300) {
                        results.push({
                            cls: (el.className || '').slice(0,80),
                            tag: el.tagName,
                            text: t.slice(0, 150)
                        });
                    }
                });
            });
            return results.slice(0, 30);
        }""")
        for item in info:
            print(f"   [{item['tag']}] cls={item['cls'][:50]}", flush=True)
            print(f"     text: {item['text'][:100]}", flush=True)

        # 查找所有链接和按钮
        print("\n8. 弹窗中的链接/按钮:", flush=True)
        links_btns = await popup.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a, button, [class*=btn]').forEach(el => {
                const t = (el.innerText || '').trim();
                if (t && t.length < 30) {
                    results.push({
                        tag: el.tagName,
                        text: t,
                        href: el.getAttribute('href') || '',
                        cls: (el.className || '').slice(0, 40)
                    });
                }
            });
            return results.slice(0, 20);
        }""")
        for lb in links_btns:
            print(f"   [{lb['tag']}] text='{lb['text']}' href='{lb['href'][:60]}'", flush=True)

        # 判断是单课程还是课程包
        is_bundle = any(kw in popup_text for kw in ["课程目录", "章节", "播放列表", "列表", "课程包", "共"])
        has_single_learn = "我要学习" in popup_text or "开始学习" in popup_text
        print(f"\n9. 判断: 课程包={'是' if is_bundle else '否'}, 单课程直接学={'是' if has_single_learn else '否'}", flush=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
