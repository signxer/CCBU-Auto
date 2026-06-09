#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
from rich.console import Console
from rich import print_json

console = Console()


async def debug_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        console.print("[bold blue]1. 导航到学习页面[/bold blue]")
        await page.goto("https://u.ccb.com/portal/#/study")
        
        console.print("\n[yellow]请在浏览器中完成登录...[/yellow]")
        console.print("[green]登录成功后按回车键继续[/green]")
        input("")
        
        console.print("\n[bold blue]2. 检查页面结构[/bold blue]")
        
        console.print("\n[bold]页面标题:[/bold]", await page.title())
        console.print("[bold]当前URL:[/bold]", page.url)
        
        console.print("\n[bold blue]3. 获取页面所有元素的标签名[/bold blue]")
        all_tags = await page.evaluate("""() => {
            const tags = new Set();
            document.querySelectorAll('*').forEach(el => tags.add(el.tagName));
            return Array.from(tags).sort();
        }""")
        console.print(all_tags)
        
        console.print("\n[bold blue]4. 导航到专题班页面[/bold blue]")
        await page.goto("https://u.ccb.com/workshop/#/index?collegeId=&departmentId=&orderby=praise")
        await asyncio.sleep(5)
        
        console.print("\n[bold blue]5. 保存页面HTML到文件[/bold blue]")
        html_content = await page.content()
        with open("page_debug.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        console.print("[green]✓ 页面HTML已保存到 page_debug.html[/green]")
        
        console.print("\n[bold blue]6. 查找页面中的所有 div 元素，看有哪些类名[/bold blue]")
        div_classes = await page.evaluate("""() => {
            const classes = new Set();
            document.querySelectorAll('div[class]').forEach(el => {
                el.className.split(' ').forEach(c => c && classes.add(c));
            });
            return Array.from(classes).sort();
        }""")
        console.print("\n[bold]找到的 div 类名:[/bold]")
        for cls in div_classes:
            console.print(f"  - {cls}")
        
        console.print("\n[bold blue]7. 查找可能包含列表的元素[/bold blue]")
        list_selectors = ['ul', 'ol', '[class*="list"]', '[class*="item"]', '[class*="card"]', '[class*="workshop"]']
        for selector in list_selectors:
            count = await page.locator(selector).count()
            if count > 0:
                console.print(f"  [cyan]{selector}[/cyan]: {count} 个元素")
        
        console.print("\n[bold blue]8. 查找页面中的文本内容，看有什么关键词[/bold blue]")
        body_text = await page.locator("body").inner_text()
        lines = [line.strip() for line in body_text.split('\n') if line.strip()]
        console.print(f"\n页面文本预览（前30行）:")
        for line in lines[:30]:
            console.print(f"  {line}")
        
        console.print("\n[yellow]调试完成！按回车键关闭浏览器...[/yellow]")
        input("")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_page())
