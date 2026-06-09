#!/usr/bin/env python3
import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

import click
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

load_dotenv()
console = Console()

# 存储文件路径
STORAGE_STATE_PATH = "ccbu_session.json"
USER_CREDENTIALS_PATH = "ccbu_credentials.json"
TAGS_STATE_PATH = "ccbu_tags.json"
CONFIG_PATH = "ccbu_config.json"


def safe_print(text, style=None):
    """安全的打印，避免Rich Markup错误"""
    try:
        if style:
            console.print(text, style=style)
        else:
            console.print(text)
    except Exception:
        # 如果Rich解析失败时，直接打印
        print(text)


DEBUG_LOG = "ccbu_debug.log"

def init_debug_log():
    # 清空调试日志
    try:
        with open(DEBUG_LOG, "w", encoding="utf-8") as f:
            f.write(f"=== CCBU-Auto Debug Log ===\n")
    except:
        pass

def debug(msg: str):
    # 写入调试日志，不显示在控制台
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except:
        pass

async def async_input(prompt: str, default: str = "y", timeout: int = 5) -> str:
    """带超时的输入，超时后自动返回默认值"""
    console.print(f"{prompt}（{timeout}秒后自动: {default}）", style="yellow", end="")
    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, lambda: input().strip().lower()),
            timeout=timeout
        )
        return result if result else default
    except asyncio.TimeoutError:
        console.print(f"[超时，自动: {default}]", style="yellow")
        return default


class CCBULearner:
    def __init__(self, headless: bool = False, workers: int = 1):
        self.headless = headless
        self.workers = workers
        self.playwright = None
        self.browser = None
        self.context = None
        self.pages: List[Page] = []
        self.study_hours = 0.0
        self.target_hours = 0.0
        self.tags_to_learn = []
        self.study_goal = 0.0  # 学习目标学时
        self.goal_type = 'central'  # 目标类型: central=集中培训 online=网络自学
        self.goal_reached = False
        self.user_data = {}

    async def init(self):
        self.playwright = await async_playwright().start()
        # Windows下自动检测系统Chrome
        import sys
        launch_opts = {"headless": self.headless}
        if sys.platform == "win32":
            try:
                import subprocess
                subprocess.run(["where", "chrome"], check=True, capture_output=True, timeout=3)
                launch_opts["channel"] = "chrome"
                console.print("使用系统Chrome", style="green")
            except:
                console.print("使用内置Chrome", style="yellow")
        self.browser = await self.playwright.chromium.launch(**launch_opts)
        
        # 创建浏览器上下文
        if os.path.exists(STORAGE_STATE_PATH):
            try:
                self.context = await self.browser.new_context(
                    storage_state=STORAGE_STATE_PATH,
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                console.print("已加载保存的会话", style="green")
            except Exception as e:
                console.print("加载会话失败，创建新会话", style="yellow")
                self.context = await self.browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        
        for i in range(self.workers):
            page = await self.context.new_page()
            self.pages.append(page)

    async def close(self):
        # 先关闭所有页面和弹窗
        if self.context:
            try:
                for p in self.context.pages:
                    try:
                        await p.close()
                    except:
                        pass
                await self.context.close()
            except:
                pass
        
        # 保存会话状态
        try:
            if self.context:
                await self.context.storage_state(path=STORAGE_STATE_PATH)
                console.print("会话已保存", style="green")
        except:
            console.print("保存会话失败", style="yellow")
        
        # 关闭浏览器
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
        
        # 停止Playwright
        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass
        
        # 强制结束chromium进程（兜底，兼容Windows）
        import subprocess, sys
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                              stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], 
                              stderr=subprocess.DEVNULL, timeout=5)
            else:
                subprocess.run(["pkill", "-f", "chrome"], stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["pkill", "-f", "chromium"], stderr=subprocess.DEVNULL, timeout=5)
        except:
            pass

    async def check_login_status(self, page: Page) -> bool:
        """检查是否已登录 - 通过页面真实DOM状态检测"""
        try:
            console.print("正在检查登录状态...", style="blue")
            await page.goto("https://u.ccb.com/portal/#/study",
                            wait_until="networkidle", timeout=30000)
            # SPA 可能需要额外时间渲染，等待关键元素出现
            await page.wait_for_timeout(5000)
            
            current_url = page.url
            debug(f"当前URL: {current_url}")
            
            # 1) 检查是否被重定向到统一登录页
            if "/sys/#/login" in current_url:
                console.print("被重定向到登录页面，判定未登录", style="yellow")
                return False
            
            # 2) 检查未登录标志元素（访客模式下页面特有）
            try:
                notlogin_tips = await page.locator(".cuWeb-swipe-web-info-notlogin-tips").count()
                notlogin_btn = await page.locator(".cuWeb-swipe-web-info-notlogin-btn").count()
                if notlogin_tips > 0 or notlogin_btn > 0:
                    console.print('发现未登录提示“登录跟进你的学习进度”，判定未登录', style='yellow')
                    return False
            except:
                pass
            
            # 3) 检查用户盒子：显示"登录"=未登录，显示用户名=已登录
            try:
                user_box_text = await page.locator(".ccb-user-box").inner_text(timeout=3000)
                if "登录" in user_box_text and len(user_box_text.strip()) < 10:
                    console.print("用户盒子显示「登录」，判定未登录", style="yellow")
                    return False
            except:
                pass
            
            # 4) 页面文本兜底判断
            page_text = await page.locator("body").inner_text(timeout=5000)
            if "立即登录" in page_text and "0学时" in page_text:
                console.print("页面显示「立即登录」且学时为0，判定未登录", style="yellow")
                return False
            
            # 5) 通过以上所有检查，再看是否有真实用户学习数据
            if "学时" in page_text and "学员" in page_text and "立即登录" not in page_text:
                console.print("检测到真实用户数据，判定已登录", style="green")
                return True
            
            console.print("未能确认登录状态，默认判定未登录", style="yellow")
            return False
        except Exception as e:
            console.print(f"检查登录状态失败: {e}", style="yellow")
            return False

    def load_user_credentials(self) -> Optional[Dict]:
        """加载保存的用户凭证"""
        if os.path.exists(USER_CREDENTIALS_PATH):
            try:
                with open(USER_CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                console.print("加载凭证失败", style="yellow")
        return None

    def save_user_credentials(self, username: str, password: str):
        """保存用户凭证"""
        try:
            with open(USER_CREDENTIALS_PATH, 'w', encoding='utf-8') as f:
                json.dump({"username": username, "password": password}, f, ensure_ascii=False, indent=2)
            console.print("凭证已保存", style="green")
        except Exception as e:
            console.print("保存凭证失败", style="yellow")

    async def login(self):
        import getpass
        
        console.print("建行学习自动登录", style="bold blue")
        
        # 先检查是否已登录
        page = self.pages[0]
        if await self.check_login_status(page):
            # 显示当前用户并询问是否切换
            try:
                _uname = ""
                try:
                    _uname = await page.locator(".ccb-user-box").inner_text(timeout=3000)
                except:
                    pass
                if not _uname:
                    try:
                        _uname = await page.evaluate("() => localStorage.getItem('userName') || ''")
                    except:
                        pass
                _uname = (_uname or "").strip()
                if _uname:
                    console.print(f"当前用户: {_uname}", style="green")
                    _switch = await async_input("是否切换用户？(y/n)", default="n", timeout=5)
                    if _switch in ('y', 'yes'):
                        try:
                            if os.path.exists(STORAGE_STATE_PATH):
                                os.remove(STORAGE_STATE_PATH)
                            await page.context.clear_cookies()
                            console.print("已清除会话，准备重新登录", style="yellow")
                        except:
                            pass
                    else:
                        console.print("✓ 继续使用当前会话", style="bold green")
                        return
                else:
                    console.print("✓ 检测到已登录状态，无需重新登录!", style="bold green")
                    return
            except:
                console.print("✓ 检测到已登录状态，无需重新登录!", style="bold green")
                return
        
        console.print("未检测到登录状态，需要登录", style="yellow")
        
        # 尝试加载已保存的凭证
        saved_credentials = self.load_user_credentials()
        use_saved = False
        
        if saved_credentials and 'username' in saved_credentials:
            console.print(f"发现已保存账号: {saved_credentials['username']}，是否使用？(y/n，默认y) ", style="yellow", end="")
            choice = input().strip().lower()
            if choice != 'n' and choice != 'no':
                use_saved = True
        
        if use_saved and saved_credentials:
            username = saved_credentials['username']
            password = saved_credentials.get('password', '')
            if not password:
                password = getpass.getpass("请输入密码: ")
        else:
            # 询问用户是自动登录还是手动登录
            console.print("是否使用自动登录？(y/n，默认y) ", style="yellow", end="")
            choice = input().strip().lower()
            
            if choice == 'n' or choice == 'no':
                # 手动登录模式
                console.print("请在打开的浏览器中完成登录...", style="bold blue")
                await page.goto("https://u.ccb.com/portal/#/study")
                
                console.print("等待登录完成...", style="yellow")
                console.print("提示：登录成功后按回车键继续", style="green")
                
                input("")
                
                console.print("✓ 登录成功!", style="bold green")
                return
            else:
                # 自动登录模式
                console.print()
                console.print("请输入建行统一认证账号: ", style="cyan", end="")
                username = input().strip()
                password = getpass.getpass("请输入密码: ")
                
                if not username or not password:
                    console.print("用户名或密码不能为空，将使用手动登录模式", style="red")
                    await self.login()
                    return
        
        # 使用自动登录流程
        console.print("正在导航到登录页面...", style="blue")
        await page.goto("https://u.ccb.com/sys/#/login")
        await asyncio.sleep(3)
        
        try:
            # 输入用户名（先移除maxlength限制，再通过原生DOM API赋值）
            console.print("正在输入用户名...", style="blue")
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
            # 验证输入是否正确
            actual_uname = await page.evaluate("""() => {
                const el = document.querySelector('input[placeholder*="账号"]');
                return el ? el.value : '';
            }""")
            console.print(f"  实际填入: [{actual_uname}]", style="blue")
            if len(actual_uname) < len(username):
                console.print("输入不完整，尝试逐字符键盘输入...", style="yellow")
                await page.keyboard.press("Meta+a")
                await page.keyboard.press("Backspace")
                await page.wait_for_timeout(300)
                await page.keyboard.type(username, delay=150)
                actual_uname = await page.evaluate("""() => {
                    const el = document.querySelector('input[placeholder*="账号"]');
                    return el ? el.value : '';
                }""")
                console.print(f"  键盘输入后: [{actual_uname}]", style="blue")
            await asyncio.sleep(0.5)
            
            # 输入密码
            console.print("正在输入密码...", style="blue")
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
            
            # 点击登录按钮
            console.print("正在点击登录按钮...", style="blue")
            login_button = page.get_by_role("button", name="登录")
            
            # 等待登录按钮可点击
            try:
                await login_button.wait_for(state="enabled", timeout=10000)
            except:
                pass
            
            await login_button.click()
            
            # 等待登录成功后保存凭证
            if not use_saved:
                console.print("是否保存账号密码以便下次使用？(y/n，默认y) ", style="yellow", end="")
                save_choice = input().strip().lower()
                if save_choice != 'n' and save_choice != 'no':
                    self.save_user_credentials(username, password)
            
            # 自动检测登录是否完成
            console.print("正在等待登录完成...", style="yellow")
            
            logged_in = False
            login_failed = False
            for i in range(60):  # 最多等待60秒
                await asyncio.sleep(1)
                try:
                    current_url = page.url
                    
                    # 如果还停留在登录页
                    if "/sys/#/login" in current_url:
                        # 检查是否有错误提示
                        try:
                            err = page.locator(".el-message--error, .el-form-item__error, [class*=error]")
                            err_text = await err.first.inner_text(timeout=1500)
                            if err_text:
                                console.print(f"[red]登录失败: {err_text.strip()}[/red]")
                                login_failed = True
                                break
                        except:
                            pass
                        if i >= 30:
                            console.print("[yellow]登录请求似乎未成功，尝试检查页面状态...[/yellow]")
                            login_failed = True
                            break
                        continue
                    
                    # URL不再是登录页 → 登录成功！导航到study页确认
                    console.print(f"检测到页面跳转: {current_url}", style="green")
                    console.print("正在导航到学习页面确认登录状态...", style="blue")
                    
                    # 导航到study页面做最终确认
                    await page.goto("https://u.ccb.com/portal/#/study",
                                    wait_until="networkidle", timeout=15000)
                    await page.wait_for_timeout(3000)
                    
                    # 用和check_login_status相同的逻辑做最终验证
                    final_url = page.url
                    if "/sys/#/login" in final_url:
                        console.print("被重定向回登录页，登录未成功", style="yellow")
                        await asyncio.sleep(3)
                        continue
                    
                    # 检查是否还有未登录标志
                    nt = await page.locator(".cuWeb-swipe-web-info-notlogin-tips").count()
                    nb = await page.locator(".cuWeb-swipe-web-info-notlogin-btn").count()
                    if nt == 0 and nb == 0:
                        try:
                            ubt = await page.locator(".ccb-user-box").inner_text(timeout=2000)
                            if "登录" not in ubt or len(ubt.strip()) >= 10:
                                logged_in = True
                                console.print("✓ 检测到登录成功!", style="bold green")
                                break
                        except:
                            pass
                        # 兜底：页面文字
                        pt = await page.locator("body").inner_text(timeout=3000)
                        if "立即登录" not in pt and ("学时" in pt or "课程" in pt):
                            logged_in = True
                            console.print("✓ 检测到登录成功!", style="bold green")
                            break
                    
                    # 如果到了这里还没确认，继续等待
                    console.print("尚未确认登录状态，继续等待...", style="yellow")
                except:
                    pass
            
            # 处理登录失败：重试
            if login_failed and not logged_in:
                console.print("[yellow]登录失败！[/yellow]")
                console.print("可能原因：账号/密码错误、网络问题或验证码", style="yellow")
                retry = input("是否重新输入账号密码重试？(y/n，默认y): ").strip().lower()
                if retry != 'n':
                    for attempt in range(3):
                        console.print(f"[bold blue]第 {attempt+1} 次重试[/bold blue]")
                        await page.goto("https://u.ccb.com/sys/#/login")
                        await asyncio.sleep(2)
                        
                        console.print("正在输入用户名...", style="blue")
                        await page.evaluate(f"""() => {{
                            const el = document.querySelector('input[placeholder*="账号"]');
                            if (el) {{
                                el.removeAttribute('maxlength');
                                el.removeAttribute('maxLength');
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, '{username}');
                                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }}
                        }}""")
                        actual_uname = await page.evaluate("""() => {
                            const el = document.querySelector('input[placeholder*="账号"]');
                            return el ? el.value : '';
                        }""")
                        if len(actual_uname) < len(username):
                            console.print("输入不完整，用键盘补充...", style="yellow")
                            await page.keyboard.press("Meta+a")
                            await page.keyboard.press("Backspace")
                            await page.wait_for_timeout(300)
                            await page.keyboard.type(username, delay=150)
                        
                        await asyncio.sleep(0.5)
                        console.print("正在输入密码...", style="blue")
                        await page.evaluate(f"""() => {{
                            const el = document.getElementById('inputPwd');
                            if (el) {{
                                el.removeAttribute('maxlength');
                                el.removeAttribute('maxLength');
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, '{password}');
                                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }}
                        }}""")
                        
                        console.print("正在点击登录按钮...", style="blue")
                        lb = page.get_by_role("button", name="登录")
                        await lb.click()
                        
                        for j in range(30):
                            await asyncio.sleep(1)
                            cu = page.url
                            if "/sys/#/login" not in cu:
                                await page.wait_for_timeout(3000)
                                nt = await page.locator(".cuWeb-swipe-web-info-notlogin-tips").count()
                                if nt == 0:
                                    logged_in = True
                                    console.print("✓ 重试登录成功!", style="bold green")
                                    break
                                break
                            # 检查错误
                            try:
                                e = page.locator(".el-message--error, .el-form-item__error")
                                t = await e.first.inner_text(timeout=1500)
                                if t:
                                    console.print(f"[red]重试失败: {t.strip()}[/red]")
                                    break
                            except:
                                pass
                        if logged_in:
                            break
                    else:
                        console.print("[yellow]多次重试失败，将使用手动登录模式[/yellow]")
            
            if not logged_in:
                console.print("[yellow]请手动在浏览器中完成登录，然后按回车键继续[/yellow]")
                input()
            
            console.print("✓ 登录流程完成!", style="bold green")
            
        except Exception as e:
            console.print("自动登录失败", style="red")
            console.print("将使用手动登录模式", style="yellow")
            console.print("请在浏览器中完成登录后按回车键继续...", style="green")
            input("")

    async def get_workshops(self, page: Page) -> List[Dict]:
        """获取专题班列表 - 从.card结构提取所有专题班"""
        workshops = []
        try:
            console.print("正在获取专题班列表...", style="blue")
            
            # 等待专题班列表容器加载
            # await page.wait_for_selector(".workshop-content-list", timeout=10000)
            try:
                await page.wait_for_selector(".workshop-content-list", timeout=10000)
            except:
                pass
            
            # 方法1：从 workshop-content-list 中提取卡片
            # 注意：DOM 结构为 .workshop-content-list > ul > li.clearfix（中间有ul层）
            cards = await page.locator(".workshop-content-list li.clearfix").all()
            console.print(f"找到 {len(cards)} 个专题班卡片元素", style="green")
            
            for card in cards:
                try:
                    # 提取标题
                    title_el = card.locator(".workshop-list-content-title")
                    title_text = await title_el.inner_text(timeout=3000)
                    
                    # 提取课程数和学时
                    info_spans = await card.locator(".workshop-list-content span").all()
                    course_count = ""
                    study_hours = ""
                    for span in info_spans:
                        text = (await span.inner_text()).strip()
                        if "总课程" in text:
                            course_count = text
                        elif "学时" in text:
                            study_hours = text
                    
                    # 提取报名状态
                    enroll_status = ""
                    try:
                        status_el = card.locator(".border-ing, .border-end")
                        enroll_status = await status_el.inner_text(timeout=2000)
                    except:
                        pass
                    
                    # 提取详情页链接
                    detail_link = ""
                    try:
                        link_el = card.locator("a").first
                        href = await link_el.get_attribute("href")
                        if href:
                            detail_link = href
                    except:
                        pass
                    
                    workshops.append({
                        "title": title_text.strip(),
                        "course_count": course_count,
                        "study_hours": study_hours,
                        "enroll_status": enroll_status.strip(),
                        "detail_link": detail_link,
                        "element": card
                    })
                except Exception as e2:
                    pass
            
            # 方法2：如果没有找到卡片，尝试从<a>标签提取（兜底）
            if not workshops:
                console.print("卡片提取未找到结果，改用链接匹配...", style="yellow")
                link_elements = await page.get_by_role("link").all()
                for link in link_elements:
                    try:
                        text = await link.inner_text()
                        if text and len(text.strip()) > 3:
                            text_clean = text.strip()[:100]
                            href = await link.get_attribute("href") or ""
                            workshops.append({
                                "title": text_clean,
                                "course_count": "",
                                "study_hours": "",
                                "enroll_status": "",
                                "detail_link": href,
                                "element": link
                            })
                    except:
                        pass
            
            console.print(f"共获取 {len(workshops)} 个专题班", style="green")
            
        except Exception as e:
            console.print("获取专题班列表失败", style="red")
            import traceback
            traceback.print_exc()
        
        return workshops

    async def go_to_next_page(self, page: Page) -> bool:
        """翻到下一页 - 检查按钮是否可用"""
        try:
            console.print("正在查找下一页按钮...", style="blue")
            
            # 方式1: 在分页区域找"下一页"
            try:
                # 分页容器结构: div.pager_manu > span.pagetext.hand
                page_container = page.locator("div.pager_manu, .pageinfo, .pagination, [class*=page]:not(.pageheader):not(.homepage_layout)")
                container_count = await page_container.count()
                
                if container_count > 0:
                    next_btn = page_container.first.locator("text=下一页")
                    if await next_btn.count() > 0:
                        btn_class = await next_btn.first.get_attribute("class") or ""
                        # 禁用态用 "disable" class（注意不是 "disabled"）
                        if "disable" not in btn_class:
                            await next_btn.first.click()
                            await page.wait_for_timeout(5000)
                            console.print("已翻到下一页", style="green")
                            return True
                        else:
                            console.print("下一页按钮不可用（disable），已到最后一页", style="yellow")
                            return False
            except Exception as e1:
                pass
            
            # 方式2: 查找span.pagetext.hand的"下一页"元素
            try:
                next_spans = page.locator("span.pagetext").filter(has_text="下一页")
                if await next_spans.count() > 0:
                    cls = await next_spans.first.get_attribute("class") or ""
                    if "disable" not in cls and await next_spans.first.is_visible():
                        await next_spans.first.click()
                        await page.wait_for_timeout(5000)
                        console.print("已翻到下一页", style="green")
                        return True
            except:
                pass
            
            # 方式3: 直接查找可点击的"下一页"元素
            try:
                next_els = page.locator("a, button, span, li").filter(has_text="下一页")
                count = await next_els.count()
                for i in range(count):
                    el = next_els.nth(i)
                    cls_str = (await el.get_attribute("class")) or ""
                    is_disabled = await el.get_attribute("disabled")
                    has_disable = "disable" in cls_str
                    is_visible = await el.is_visible()
                    if is_visible and not is_disabled and not has_disable:
                        await el.click()
                        await page.wait_for_timeout(5000)
                        console.print("已翻到下一页", style="green")
                        return True
            except:
                pass
            
            console.print("未找到可用的下一页按钮，已到最后一页", style="yellow")
            return False
        except Exception as e:
            console.print(f"翻页失败: {e}", style="yellow")
            return False

    async def display_workshops(self, workshops: List[Dict]):
        table = Table(title="专题班列表")
        table.add_column("序号", style="cyan")
        table.add_column("专题班名称", style="magenta")
        table.add_column("进度", style="green")
        
        for i, workshop in enumerate(workshops, 1):
                    table.add_row(
                str(i),
                workshop["title"][:60],
                workshop.get("study_hours", workshop.get("progress", "未知"))
            )
        
        console.print(table)

    async def filter_by_tags(self, page: Page):
        """根据标签筛选专题班"""
        if not self.tags_to_learn:
            return
        
        console.print(f"正在筛选标签: {', '.join(self.tags_to_learn)}", style="blue")
        
        try:
            await page.wait_for_timeout(3000)
            
            for tag in self.tags_to_learn:
                console.print(f"查找标签: {tag}", style="blue")
                
                found = False
                
                # 方法1：在 tag-tree-list 中查找 span.single-tag 匹配文本
                for attempt in range(3):
                    try:
                        all_tags = page.locator("ul.tag-tree-list span.single-tag")
                        cnt = await all_tags.count()
                        debug(f"tag-tree-list: {cnt} spans")
                        for i in range(cnt):
                            text = (await all_tags.nth(i).inner_text()).strip()
                            if text == tag:
                                console.print(f"  找到匹配标签: {text}", style="green")
                                await all_tags.nth(i).click()
                                await page.wait_for_timeout(3000)
                                console.print(f"  ✓ 已点击标签: {tag}", style="green")
                                found = True
                                break
                        if found:
                            break
                    except Exception as e1:
                        console.print(f"  方法1尝试 {attempt+1} 失败: {e1}", style="yellow")
                    await page.wait_for_timeout(2000)
                
                if found:
                    continue
                
                # 方法2：在全页面范围找匹配文本的可见clickable元素
                for attempt in range(3):
                    try:
                        console.print(f"  方法2: 页面搜索标签...", style="blue")
                        candidates = page.locator("span, div, li, a").filter(has_text=tag)
                        cc = await candidates.count()
                        console.print(f"  找到 {cc} 个候选元素", style="blue")
                        for j in range(min(cc, 20)):
                            try:
                                t = (await candidates.nth(j).inner_text()).strip()
                                if t == tag and await candidates.nth(j).is_visible():
                                    console.print(f"  找到可见标签元素: {tag}", style="green")
                                    await candidates.nth(j).click()
                                    await page.wait_for_timeout(3000)
                                    console.print(f"  ✓ 已点击标签: {tag}", style="green")
                                    found = True
                                    break
                            except:
                                pass
                        if found:
                            break
                    except:
                        pass
                    await page.wait_for_timeout(2000)
                
                if not found:
                    console.print(f"  未找到标签: {tag}", style="yellow")
            
            console.print("标签筛选完成", style="green")
        except Exception as e:
            console.print(f"标签筛选失败: {e}，将使用所有专题班", style="yellow")
            import traceback
            traceback.print_exc()

    async def enroll_workshop(self, page: Page, workshop_title: str):
        """报名专题班 - 进入专题班详情页，点击报名/学习"""
        try:
            console.print(f"正在查找并点击专题班: {workshop_title}", style="blue")
            
            initial_pages_count = len(self.context.pages)
            
            # 查找并点击专题班链接
            workshop_link = None
            # 方法1: 通过卡片中的详细链接点击
            try:
                card = page.locator(f"text={workshop_title}").first
                if await card.count() > 0:
                    workshop_link = card
            except:
                pass
            # 方法2: 遍历所有链接
            if not workshop_link or await workshop_link.count() == 0:
                all_links = await page.get_by_role("link").all()
                for link in all_links:
                    try:
                        text = await link.inner_text()
                        if workshop_title in text:
                            workshop_link = link
                            break
                    except:
                        pass
            
            if not workshop_link or (hasattr(workshop_link, 'count') and await workshop_link.count() == 0):
                console.print("未找到专题班链接", style="red")
                return False, page
            
            console.print("找到专题班链接，准备点击", style="green")
            
            # 点击链接（SPA 页面，不需要 expect_navigation）
            await workshop_link.click()
            await page.wait_for_timeout(8000)
            
            debug(f"当前页面URL: {page.url}")
            
            # 检查是否打开了新标签页
            working_page = page
            if len(self.context.pages) > initial_pages_count:
                working_page = self.context.pages[-1]
                await working_page.bring_to_front()
                await working_page.wait_for_timeout(3000)
                debug(f"新标签页URL: {working_page.url[:80]}")
            
            # 获取页面内容
            page_text = await working_page.locator("body").inner_text(timeout=5000)
            debug(f"页面标题预览: {page_text[:100]}")
            
            # 检查登录态
            if "密码登录" in page_text[:500]:
                console.print("页面显示登录表单，需要重新登录", style="red")
                return False, working_page
            
            # 判断是否已报名（看URL是否已跳转到myworkshop）
            current_url = working_page.url
            already_enrolled = "/myworkshop/" in current_url
            
            if already_enrolled:
                console.print("该专题班已报名", style="green")
                return True, working_page
            
            # 检查页面上是否有立即报名按钮
            async def has_enroll_btn():
                for kw in ["立即报名", "加入学习", "免费报名", "开始学习"]:
                    try:
                        btn = working_page.locator(f"text={kw}").first
                        if await btn.count() > 0:
                            try:
                                if await btn.is_visible():
                                    return kw, btn
                            except:
                                return kw, btn
                    except:
                        pass
                return None, None
            
            kw, btn_el = await has_enroll_btn()
            if not btn_el:
                console.print("未找到报名按钮，可能已报名或在已报名页", style="yellow")
                return True, working_page
            
            console.print(f"找到「{kw}」按钮，准备点击", style="blue")
            
            # 点击并验证
            enrolled = False
            for attempt in range(3):
                # 方法1：直接点击找到的元素
                try:
                    await btn_el.click()
                    await working_page.wait_for_timeout(3000)
                except:
                    pass
                
                # 验证：看URL是否跳转、按钮是否消失
                new_url = working_page.url
                kw2, _ = await has_enroll_btn()
                if "/myworkshop/" in new_url or not kw2:
                    enrolled = True
                    console.print(f"✓ 报名成功！URL: {new_url[:80]}", style="bold green")
                    break
                
                # 方法2：尝试点击元素的父级
                try:
                    parent = btn_el.locator("..")
                    if await parent.count() > 0:
                        await parent.first.click()
                        await working_page.wait_for_timeout(3000)
                        new_url = working_page.url
                        kw2, _ = await has_enroll_btn()
                        if "/myworkshop/" in new_url or not kw2:
                            enrolled = True
                            console.print("✓ 报名成功（通过父元素点击）", style="bold green")
                            break
                except:
                    pass
                
                # 方法3：用JS触发点击
                try:
                    await working_page.evaluate(f"""() => {{
                        const els = document.querySelectorAll('*');
                        for (const el of els) {{
                            if (el.innerText.includes('{kw}') && el.offsetParent !== null) {{
                                el.click();
                                el.dispatchEvent(new Event('click', {{ bubbles: true }}));
                                // 也点一下父级
                                if (el.parentElement) el.parentElement.click();
                                break;
                            }}
                        }}
                    }}""")
                    await working_page.wait_for_timeout(3000)
                    new_url = working_page.url
                    kw2, _ = await has_enroll_btn()
                    if "/myworkshop/" in new_url or not kw2:
                        enrolled = True
                        console.print("✓ 报名成功（通过JS点击）", style="bold green")
                        break
                except:
                    pass
                
                if attempt < 2:
                    console.print(f"尝试 {attempt+1} 未生效，重试...", style="yellow")
                    await working_page.wait_for_timeout(2000)
            
            if enrolled:
                # 等页面加载课程内容
                await working_page.wait_for_timeout(3000)
                return True, working_page
            else:
                console.print("报名按钮点击后未检测到变化，手动确认", style="yellow")
                console.print("报名后按回车键继续（或等待5秒自动继续）...", style="yellow", end="")
                try:
                    await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, input), timeout=5)
                except asyncio.TimeoutError:
                    pass
                return True, working_page
            
        except Exception as e:
            console.print(f"进入专题班失败: {e}", style="red")
            import traceback
            traceback.print_exc()
            return False, page

    async def find_and_learn_courses(self, page: Page, worker_id: int):
        """学习课程 - 获取课程列表后启动并行学习（失败自动重试5次）"""
        try:
            console.print(f"正在获取课程列表...", style="blue")
            
            # 获取专题班ID
            workshop_id = ""
            url = page.url
            import re as _re
            m = _re.search(r'id=([a-f0-9\-]+)', url)
            if m:
                workshop_id = m.group(1)
            if not workshop_id:
                console.print("无法获取专题班ID", style="red")
                return False
            
            # 多次尝试获取课程列表（表格可能是异步加载的）
            courses = []
            for attempt in range(5):
                if attempt > 0:
                    console.print(f"第 {attempt+1} 次尝试获取课程列表...", style="yellow")
                    await page.reload(wait_until="networkidle")
                    await page.wait_for_timeout(5000)
                
                courses = await self.get_courses_from_workshop(page)
                if courses:
                    break
            
            await self.display_course_table(courses)
            
            if not courses:
                console.print("重试5次后仍未获取到课程", style="red")
                return False
            
            # 启动并行学习
            await self.parallel_learn_courses(workshop_id, courses)
            return True
            
        except Exception as e:
            console.print(f"学习课程失败: {e}", style="red")
            import traceback
            traceback.print_exc()
            return False


    async def _set_lowest_quality(self, page: Page):
        # 静音 + 最低画质 + 2倍速度
        try:
            # JS静音（最可靠）
            await page.evaluate("() => { const v = document.querySelector('video'); if (v) v.muted = true; }")
        except:
            pass
        try:
            # 点击音量按钮静音（兜底）
            vol_btn = page.locator('.prism-volume, .volume-icon').first
            if await vol_btn.count() > 0:
                await vol_btn.click(force=True)
                await page.wait_for_timeout(300)
        except:
            pass
        try:
            # hover播放器使控制栏可见
            try:
                await page.locator(".prism-player, video, #player_area").first.hover()
                await page.wait_for_timeout(500)
            except:
                pass
            
            # 最低画质
            qbtn = page.locator('.current-quality').first
            if await qbtn.count() > 0:
                await qbtn.click(force=True)
                await page.wait_for_timeout(1500)
                items = page.locator('.quality-list li')
                cnt = await items.count()
                if cnt > 1:
                    lowest = items.nth(cnt - 1)
                    text = await lowest.inner_text()
                    debug(f"画质: {cnt}个, 选: {text.strip()}")
                    await lowest.click(force=True)
                    await page.wait_for_timeout(2000)
        except Exception as _qe:
            debug(f"画质异常: {_qe}")

        try:
            # 2倍速度
            rate_btn = page.locator('.current-rate').first
            if await rate_btn.count() > 0:
                cur = (await rate_btn.inner_text()).strip()
                if '2' not in cur:
                    await rate_btn.click(force=True)
                    await page.wait_for_timeout(1500)
                    opt = page.locator('li[data-rate="2.0"]').first
                    if await opt.count() > 0:
                        await opt.click(force=True)
                        await page.wait_for_timeout(500)
                        debug("✅ 已设为2倍速度")
        except Exception as _se:
            debug(f"倍速异常: {_se}")


    async def _check_video_progress(self, page: Page) -> float:
        # 检查当前课程的播放进度（async 版本）
        try:
            # 方法1: 右上角学习进度文字
            pct = await page.evaluate('''() => {
                const el = document.querySelector('.el-progress__text');
                if (el) {
                    const t = el.innerText.trim().replace('%', '');
                    const n = parseFloat(t);
                    if (!isNaN(n)) return n;
                }
                return -1;
            }''')
            if isinstance(pct, (int, float)) and pct >= 0:
                return float(pct)
        except:
            pass

        try:
            # 方法2: HTML5 video
            prog = await page.evaluate('''() => {
                const v = document.querySelector('video');
                if (v && v.duration && v.duration > 0 && v.currentTime > 0)
                    return (v.currentTime / v.duration) * 100;
                return -1;
            }''')
            if isinstance(prog, (int, float)) and prog >= 0:
                return round(float(prog), 1)
        except:
            pass

        try:
            # 方法3: 页面中带百分号的文本
            text = await page.evaluate('() => document.body.innerText')
            if isinstance(text, str):
                import re
                for m in re.finditer(r'(\d+\.?\d*)\s*%', text):
                    val = float(m.group(1))
                    if 0 <= val <= 100:
                        return val
        except:
            pass

        return -1

    async def find_and_play_video(self, page: Page, worker_id: int):
        # 查找并播放视频，监控进度到100%
        try:
            debug(f"[工作线程 {worker_id+1}] 正在查找视频元素...")

            for sel in ["video", "audio", "[class*='video']", "[class*='audio']", ".prism-player"]:
                try:
                    v = await page.query_selector(sel)
                    if v:
                        debug(f"[工作线程 {worker_id+1}] 找到视频元素: {sel}")
                        try:
                            await v.click()
                        except:
                            pass
                        try:
                            await page.evaluate("v => { try { v.play(); } catch(e) {} }", v)
                        except:
                            pass
                        break
                except:
                    pass
            else:
                console.print(f"[工作线程 {worker_id+1}] 未找到视频", style="yellow")
                return False

            console.print(f"[工作线程 {worker_id+1}] 监控学习进度...", style="green")
            await self._set_lowest_quality(page)

            for check in range(120):
                await asyncio.sleep(30)
                progress = await self._check_video_progress(page)
                if isinstance(progress, (int, float)) and progress >= 0:
                    if progress >= 100:
                        console.print(f"[工作线程 {worker_id+1}] 学习进度: {progress:.0f}% 完成!", style="bold green")
                        return True
                    if check % 2 == 0:
                        console.print(f"[工作线程 {worker_id+1}] 学习进度: {progress:.0f}%", style="blue")
                elif check % 2 == 0:
                    console.print(f"[工作线程 {worker_id+1}] 学习中 (第 {(check+1)*30}s)", style="yellow")

            console.print(f"[工作线程 {worker_id+1}] 学习时长达到上限，结束", style="yellow")
            return True
        except Exception as e:
            debug(f"[工作线程 {worker_id+1}] 视频播放异常: {e}")
            import traceback
            traceback.print_exc()
            return False


    async def get_courses_from_workshop(self, page: Page) -> List[Dict]:
        # 从表格提取全部课程信息（不含URL，URL由collector动态采集）
        courses = []
        try:
            debug("正在获取课程列表...")
            await page.wait_for_timeout(3000)

            rows_data = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('tr.text-center').forEach(tr => {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length < 4) return;
                    const typeCell = cells[0].querySelector('.course-type');
                    const pct = cells[4].querySelector('.percent-text');
                    const actionSpan = cells[5].querySelector('.edit-block');
                    results.push({
                        type: typeCell ? typeCell.innerText.trim() : cells[0].innerText.trim(),
                        title: cells[1].innerText.trim(),
                        required: cells[2].innerText.trim(),
                        hours: cells[3].innerText.trim(),
                        progress: pct ? pct.innerText.trim() : cells[4].innerText.trim(),
                        action: actionSpan ? actionSpan.innerText.trim() : cells[5].innerText.trim()
                    });
                });
                return results;
            }""")

            for row in rows_data:
                title = row.get('title', '').strip()
                ctype = row.get('type', '').strip()
                # 排除图书/图书包
                if '图书' in ctype or ctype in ('考试', 'scorm'):
                    debug(f"跳过图书: {title[:40]}")
                    continue
                if title and len(title) > 3:
                    courses.append(row)

            console.print(f"课程列表: {len(courses)} 门", style="green")
        except Exception as e:
            console.print(f"获取课程列表失败: {e}", style="yellow")
            import traceback
            traceback.print_exc()

        return courses

    async def display_course_table(self, courses: List[Dict]):
        """显示课程表格"""
        if not courses:
            console.print("未获取到课程", style="yellow")
            return
        
        table = Table(title="课程列表（共{}门）".format(len(courses)))
        table.add_column("#", style="cyan", width=3)
        table.add_column("类型", style="blue", width=6)
        table.add_column("课程名称", style="white")
        table.add_column("学时", style="green", width=6)
        table.add_column("进度", style="magenta", width=8)
        table.add_column("操作", style="yellow", width=10)
        
        # 排除图书类型（显示时过滤）
        _display_courses = [c for c in courses if '图书' not in c.get('type', '')]
        for i, c in enumerate(_display_courses, 1):
                    table.add_row(
                str(i),
                c.get('type', '')[:4],
                c.get('title', '')[:50],
                c.get('hours', ''),
                c.get('progress', ''),
                c.get('action', '')
            )
        
        console.print(table)
        
        # 统计
        total = len(courses)
        to_learn = sum(1 for c in courses if c.get('action', '') == '立即学习')
        learning = sum(1 for c in courses if c.get('action', '') == '继续学习')
        done = sum(1 for c in courses if c.get('action', '') == '立即回看' or c.get('progress', '').rstrip('%').isdigit() and int(c.get('progress', '0').rstrip('%')) >= 100)
        console.print(f"总计 {total} 门，待学习 {to_learn} 门，学习中 {learning} 门，已完成 {done} 门", 
                     style="bold blue")


    async def _get_study_hours(self, page) -> dict:
        # 从学习中心获取今年的培训学时
        try:
            await page.goto("https://u.ccb.com/portal/#/studyCenter",
                           wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(5000)
            text = await page.locator("body").inner_text(timeout=5000)
        except Exception as _ex:
            debug(f"学习中心加载失败: {_ex}")
            return {"central": 0, "online": 0, "total": 0}
        
        import re as _re
        central = 0.0
        online = 0.0
        debug(f"学习中心页面内容:\n{text[:600]}")
        
        # 方法1: 找"今年已训"文本并解析
        if "今年已训" in text:
            after = text.split("今年已训")[1]
            if "完成进度" in after:
                after = after.split("完成进度")[0]
            nums = _re.findall(r'([\d.]+)\s*学时', after)
            if len(nums) >= 1:
                central = float(nums[0])
            if len(nums) >= 2:
                online = float(nums[1])
        else:
            # 方法2: 查找页面中的所有数字+学时
            debug(f"学习中心未找到[今年已训]，检查页面文本")
            nums = _re.findall(r'([\d.]+)\s*学时', text)
            debug(f"找到学时数字: {nums}")
            if len(nums) >= 4:
                # 格式: 应完成X学时, 应完成Y学时, 已训A学时, 已训B学时
                central = float(nums[2]) if len(nums) > 2 else 0
                online = float(nums[3]) if len(nums) > 3 else 0
        
        debug(f"学时解析: 集中培训={central}, 网络自学={online}")
        return {"central": central, "online": online, "total": central + online}

    async def _course_mode(self, page: Page):
        # 从 /course/#/list/1 选择课程学习
        console.print("课程列表模式", style="bold")
        list_url = "https://u.ccb.com/course/#/list/1"
        await page.goto(list_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # 课程列表交互式筛选（与专题班标签同结构）
        console.print("是否筛选课程？(y/n，默认n)（5秒后自动: n）: ", style="yellow", end="")
        _fk = input().strip().lower()
        if _fk in ('y', 'yes'):
            await page.wait_for_timeout(2000)
            # 提取tag-second过滤项
            _fitems = page.locator("li.tag-second:not(.active)")
            _fc = await _fitems.count()
            if _fc > 0:
                console.print("\n可选筛选条件:", style="bold")
                _all_flt = []
                for _fi in range(_fc):
                    _txt = (await _fitems.nth(_fi).inner_text()).strip()
                    console.print(f"  [{_fi+1:3d}] {_txt[:25]}", style="white")
                    _all_flt.append(_fitems.nth(_fi))
                console.print("输入编号（逗号分隔，回车跳过）: ", style="yellow", end="")
                _sel = input().strip()
                for _part in _sel.split(","):
                    _part = _part.strip()
                    if _part.isdigit() and 1 <= int(_part) <= len(_all_flt):
                        await _all_flt[int(_part)-1].click()
                        await page.wait_for_timeout(1500)
                await page.wait_for_timeout(3000)
            else:
                console.print("未找到筛选选项", style="yellow")

        console.print("正在提取课程列表...", style="blue")
        courses_data = []
        
        # 分页收集
        _max_page = 1
        try:
            # 等待分页栏出现
            await page.wait_for_selector("[class*=page-next], [class*=page_num]", timeout=10000)
            if await page.locator("[class*=page-next]").count() > 0:
                _pn = page.locator("[class*=page_num]")
                _tp = await _pn.count()
                if _tp > 0:
                    _lt = (await _pn.nth(_tp - 1).inner_text()).strip()
                    if _lt.isdigit():
                        console.print(f"当前显示约 {_lt} 页", style="blue")
                        console.print("获取前几页？(回车=1，0=全部): ", style="yellow", end="")
                        _ip = input().strip()
                        _max_page = int(_lt) if _ip == "0" else (int(_ip) if _ip.isdigit() and int(_ip) > 0 else 1)
        except:
            debug("未检测到分页控件，尝试文本检测")
            _body = await page.locator("body").inner_text()
            if "下一页" in _body or "下一页" in _body:
                console.print("检测到分页，获取前几页？(回车=1，0=全部): ", style="yellow", end="")
                _ip = input().strip()
                _max_page = 999 if _ip == "0" else (int(_ip) if _ip.isdigit() and int(_ip) > 0 else 1)
            else:
                debug("页面无分页")
        
        for _pg in range(_max_page):
            if _pg > 0:
                try:
                    _nb = page.locator("[class*=page-next]:not([class*=page_disabled])")
                    if await _nb.count() > 0:
                        await _nb.first.click()
                        await page.wait_for_timeout(5000)
                    else:
                        break
                except:
                    break
            
            _cards = page.locator("a.p-cursor[title]")
            _cc = await _cards.count()
            for _ci in range(_cc):
                _t = await _cards.nth(_ci).get_attribute("title")
                if _t:
                    courses_data.append({"title": _t.strip()[:60], "hours": ""})

        if not courses_data:
            console.print("未获取到课程", style="yellow")
            return

        console.print(f"找到 {len(courses_data)} 门课程:", style="green")
        for i, c in enumerate(courses_data, 1):
            console.print(f"  [{i:3d}] {c['title']}", style="white")

        console.print()
        console.print("输入课程编号（逗号/范围分隔，回车全学）: ", style="yellow", end="")
        sel = input().strip()
        indices = list(range(len(courses_data)))
        if sel:
            indices = []
            for p in sel.split(","):
                p = p.strip()
                if "-" in p:
                    a, b = p.split("-", 1)
                    indices.extend(range(int(a)-1, int(b)))
                elif p.isdigit():
                    indices.append(int(p)-1)
            indices = [i for i in indices if 0 <= i < len(courses_data)]

        nw = min(self.workers, len(indices))
        console.print(f"使用 {nw} 个工作线程学习 {len(indices)} 门课程", style="bold blue")

        async def cworker(wid, wp, aidx):
            for gi in aidx:
                c = courses_data[gi]
                console.print(f"[工作线程 {wid+1}] {c['title'][:35]}", style="bold blue")
                try:
                    await wp.goto(list_url, wait_until="networkidle", timeout=20000)
                    await wp.wait_for_timeout(5000)
                    links = wp.locator("a.p-cursor[title]")
                    if gi >= await links.count():
                        continue
                    async with wp.expect_event("popup", timeout=20000) as pi:
                        await links.nth(gi).click()
                    cp = await pi.value
                    await cp.wait_for_load_state()
                    await cp.wait_for_timeout(5000)
                    for kw in ["我要学习", "开始学习", "进入课程", "继续学习", "学习课程"]:
                        try:
                            sb = cp.locator(f"text={kw}").first
                            if await sb.count() > 0:
                                debug(f"找到 {kw}")
                                await sb.click()
                                await cp.wait_for_timeout(5000)
                                break
                        except:
                            pass
                    await self.find_and_play_video(cp, wid)
                    try:
                        await cp.close()
                    except:
                        pass
                except Exception as e:
                    debug(f"课程异常: {e}")

                # 检查学习目标
                if self.study_goal > 0 and not self.goal_reached:
                    h = await self._get_study_hours(wp)
                    cur = h.get("online", 0)
                    console.print(f"网络自学: {cur:.1f}/{self.study_goal} 学时", style="blue")
                    if cur >= self.study_goal:
                        console.print("已达到学习目标! 程序退出", style="bold green")
                        import sys
                        sys.exit(0)

        tasks = []
        for wid in range(nw):
            aidx = [indices[j] for j in range(wid, len(indices), nw)]
            tasks.append(asyncio.create_task(cworker(wid, self.pages[wid], aidx)))
            await asyncio.sleep(3)
        await asyncio.gather(*tasks)
        console.print("课程模式学习完成", style="bold green")

    async def parallel_learn_courses(self, workshop_id: str, courses: List[Dict]):
        # 每个工作线程独立操作：导航到专题班页 → 点击课程 → 处理弹窗 → 播放视频
        to_learn = [(i, c) for i, c in enumerate(courses) if c.get('action', '') in ('立即学习', '继续学习')]
        if not to_learn:
            console.print("没有需要学习的课程", style="green")
            return

        num_workers = min(self.workers, len(to_learn))
        console.print(f"[bold]使用 {num_workers} 个工作线程并行学习 {len(to_learn)} 门课程[/bold]")

        workshop_url = f"https://u.ccb.com/workshop/#/myworkshop/detail?id={workshop_id}"

        async def worker_flow(w_id: int, page: Page, assigned: List):
            for course_idx, (global_idx, course) in enumerate(assigned):
                title = course['title'][:40]
                console.print(f"[工作线程 {w_id+1}] [{course_idx+1}/{len(assigned)}] {title}", style="bold blue")

                # 1) 导航到专题班页
                try:
                    await page.goto(workshop_url, wait_until="networkidle", timeout=20000)
                    await page.wait_for_selector("tr.text-center", timeout=15000)
                    await page.wait_for_timeout(3000)
                except:
                    debug(f"[工作线程 {w_id+1}] 页面加载失败，跳过")
                    continue

                # 2) 在表格中找到课程并点击（会打开新标签页）
                rows = page.locator("tr.text-center")
                if global_idx >= await rows.count():
                    continue
                row = rows.nth(global_idx)
                btn = row.locator("span.edit-block").first
                if await btn.count() == 0:
                    continue

                try:
                    async with page.expect_event("popup", timeout=20000) as pi:
                        await btn.click()
                    course_page = await pi.value
                    await course_page.wait_for_load_state()
                    debug(f"[工作线程 {w_id+1}] 打开课程标签页")
                except:
                    debug(f"[工作线程 {w_id+1}] 未打开课程标签页，跳过")
                    continue

                # 3) 在课程页找学习按钮
                for kw in ["我要学习", "开始学习", "进入课程", "继续学习", "学习课程", "进入课程学习"]:
                    try:
                        await course_page.wait_for_selector(f"text={kw}", timeout=10000)
                        sb = course_page.locator(f"text={kw}").first
                        if await sb.count() > 0:
                            debug(f"[工作线程 {w_id+1}] 找到「{kw}」")
                            await sb.click()
                            await course_page.wait_for_timeout(5000)
                            break
                    except:
                        pass

                # 4) 播放视频（在课程标签页上）
                await self.find_and_play_video(course_page, w_id)

                # 5) 关闭课程标签页
                try:
                    await course_page.close()
                except:
                    pass

                # 检查学习目标（专题班模式→集中培训）
                if self.study_goal > 0 and not self.goal_reached:
                    _h = await self._get_study_hours(page)
                    _cur = _h.get("central", 0)
                    console.print(f"集中培训: {_cur:.1f}/{self.study_goal} 学时", style="blue")
                    if _cur >= self.study_goal:
                        console.print("已达到学习目标! 程序退出", style="bold green")
                        import sys
                        sys.exit(0)
                        
        lesson_queue = asyncio.Queue()
        tasks = []
        for w_id in range(num_workers):
            assigned = [to_learn[j] for j in range(w_id, len(to_learn), num_workers)]
            tasks.append(asyncio.create_task(worker_flow(w_id, self.pages[w_id], assigned)))
            await asyncio.sleep(3)

        # 创建处理课程包的工作线程
        async def bundle_worker(bw_id: int, bpage: Page, btotal: int):
            while True:
                item = await lesson_queue.get()
                if item is None:
                    lesson_queue.task_done()
                    break
                _, b_url, li = item
                console.print(f"[工作线程 {bw_id+1}] 课程包课时 #{li+1}", style="bold blue")
                try:
                    await bpage.goto(b_url, wait_until="networkidle", timeout=20000)
                    await bpage.wait_for_timeout(5000)
                    # 点击课时（点击后弹窗自动跳转到视频页）
                    less_el = bpage.locator(".lesson-name").nth(li)
                    if await less_el.count() == 0:
                        lesson_queue.task_done()
                        continue
                    async with bpage.expect_event("popup", timeout=20000) as pi:
                        await less_el.click()
                    video_page = await pi.value
                    await video_page.wait_for_load_state()
                    await self.find_and_play_video(video_page, bw_id)
                    try:
                        await video_page.close()
                    except:
                        pass
                except Exception as e:
                    debug(f"课时学习异常: {e}")
                lesson_queue.task_done()

        # 取当前worker数量
        bw_num = min(num_workers, 2)
        bw_tasks = []
        for bw_id in range(bw_num):
            bw_tasks.append(asyncio.create_task(bundle_worker(bw_id, self.pages[bw_id], 0)))

        # 等待所有任务完成
        await asyncio.gather(*tasks)
        await lesson_queue.join()
        for _ in range(bw_num):
            await lesson_queue.put(None)
        await asyncio.gather(*bw_tasks)
        console.print("[bold green]所有课程学习任务已完成[/bold green]")

    async def get_available_tags(self, page: Page) -> Dict[str, List[str]]:
        # 从页面提取所有可见标签，按分类分组
        try:
            tags_dict = await page.evaluate('''() => {
                const result = {};
                const cats = document.querySelectorAll('ul.tag-tree-list > li');
                cats.forEach(cat => {
                    const titleEl = cat.querySelector('.portal-title');
                    if (!titleEl) return;
                    const category = titleEl.innerText.trim();
                    if (!category) return;
                    const tags = [];
                    const items = cat.querySelectorAll('li.tag-second span.single-tag');
                    items.forEach(span => {
                        const text = span.innerText.trim();
                        if (text) tags.push(text);
                    });
                    if (tags.length > 0) result[category] = tags;
                });
                return result;
            }''')
            return tags_dict
        except Exception as e:
            console.print(f"获取标签列表失败: {e}", style="yellow")
            return {}

            console.print(f"获取标签列表失败: {e}", style="yellow")
            return {}

    async def interactive_tag_selection(self, page: Page) -> List[str]:
        # 等待标签树加载
        try:
            await page.wait_for_selector("ul.tag-tree-list", timeout=15000)
            await page.wait_for_timeout(3000)
        except:
            console.print("标签树未加载，尝试从页面文本提取标签...", style="yellow")
            # 尝试从文本提取（兜底）
            _txt = await page.locator("body").inner_text()
            _cats = {}
            _current_cat = ""
            for _ln in _txt.split("\n"):
                _ln = _ln.strip()
                if _ln in ("岗位标签", "党性教育", "研修院", "平台", "学科"):
                    _current_cat = _ln
                    _cats[_current_cat] = []
                elif _current_cat and _ln and len(_ln) < 30 and _ln != "不限":
                    _cats[_current_cat].append(_ln)
            if any(v for v in _cats.values()):
                console.print("从文本提取成功", style="green")
                tags_by_category = _cats
            else:
                console.print("无法获取标签", style="yellow")
                return []
        

        # 如果文本兜底已提取到标签，跳过DOM查询
        if 'tags_by_category' not in dir() or not tags_by_category:
            tags_by_category = await self.get_available_tags(page)
        if not tags_by_category:
            console.print("未获取到可用标签", style="yellow")
            return []
        
        all_tags = []
        idx = 1
        
        console.print()
        console.print("[bold]可用的标签分类:[/bold]", style="blue")
        
        for category, tags in tags_by_category.items():
            for tag in tags:
                console.print(f"  [{idx:3d}] {category} → {tag}", style="white")
                all_tags.append(tag)
                idx += 1
        
        console.print()
        console.print("请输入要筛选的标签编号（多个用逗号分隔，直接回车跳过）: ", style="yellow", end="")
        choice = await async_input("输入编号（逗号分隔，直接回车跳过）", default="", timeout=30)
        if not choice:
            console.print("跳过标签筛选", style="yellow")
            return []
        
        selected_indices = []
        for part in choice.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(all_tags):
                selected_indices.append(int(part) - 1)
        
        selected_tags = [all_tags[i] for i in selected_indices]
        if selected_tags:
            self.tags_to_learn = selected_tags
            console.print(f"已选择标签: {', '.join(selected_tags)}", style="green")
        return selected_tags
    async def start_learning(self, workshops: List[Dict]):
        """(已废弃) 改用直接流程"""
        if not workshops:
            console.print("未找到专题班", style="yellow")

    async def get_study_hours(self) -> float:
        page = self.pages[0]
        try:
            await page.goto("https://u.ccb.com/portal/#/studyCenter")
            await asyncio.sleep(5)
            
            body_text = await page.locator("body").inner_text()
            console.print("学习中心页面内容预览: " + body_text[:300], style="blue")
            
        except Exception as e:
            console.print("获取学时失败", style="red")
        
        return 0.0


@click.group()
def cli():
    """建行学习自动学习工具"""
    pass


@cli.command()
@click.option("--headless", is_flag=True, help="隐藏浏览器界面")
@click.option("--workers", default=1, help="同时学习的页面数量")
@click.option("--target-hours", default=0.0, help="目标学习学时，0表示不限制")
@click.option("--tags", multiple=True, help="要学习的标签，例如：党的创新理论教育 党性教育")
def start(headless, workers, target_hours, tags):
    """开始自动学习"""
    async def run():
        # 运行时询问worker数量和headless配置
        _w, _h = workers, headless
        if workers == 1 and not headless:  # 用户没有用参数，就询问
            _saved = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
                        _saved = json.load(_f)
                except:
                    pass
            if _saved.get("workers") is not None or _saved.get("headless") is not None:
                _sw = _saved.get("workers", 1)
                _sh = _saved.get("headless", False)
                console.print(f"发现上次配置: 工作线程={_sw}, 无头模式={'是' if _sh else '否'}", style="green")
                _use = await async_input("使用上次配置？(y/n)", default="y", timeout=5)
                if _use in ('y', 'yes', ''):
                    _w, _h = _sw, _sh
                else:
                    print()
                    console.print("工作线程数量 (默认1): ", style="yellow", end="")
                    _wi = input().strip()
                    if _wi.isdigit() and int(_wi) > 0:
                        _w = int(_wi)
                    console.print("无头模式 (浏览器不显示界面)？(y/n，默认n): ", style="yellow", end="")
                    _hi = input().strip().lower()
                    _h = _hi in ('y', 'yes')
                    # 保存配置
                    try:
                        with open(CONFIG_PATH, "w", encoding="utf-8") as _f:
                            json.dump({"workers": _w, "headless": _h}, _f, ensure_ascii=False, indent=2)
                        console.print("配置已保存", style="green")
                    except:
                        pass
            else:
                print()
                console.print("工作线程数量 (默认1): ", style="yellow", end="")
                _wi = input().strip()
                if _wi.isdigit() and int(_wi) > 0:
                    _w = int(_wi)
                console.print("无头模式 (浏览器不显示界面)？(y/n，默认n): ", style="yellow", end="")
                _hi = input().strip().lower()
                _h = _hi in ('y', 'yes')
                try:
                    with open(CONFIG_PATH, "w", encoding="utf-8") as _f:
                        json.dump({"workers": _w, "headless": _h}, _f, ensure_ascii=False, indent=2)
                    console.print("配置已保存", style="green")
                except:
                    pass
        
        console.print(f"运行配置: 工作线程={_w}, 无头模式={'是' if _h else '否'}", style="blue")
        learner = CCBULearner(headless=_h, workers=_w)
        learner.target_hours = target_hours
        learner.tags_to_learn = list(tags)
        
        try:
            await learner.init()
            await learner.login()
            
            # 学习目标设置
            try:
                _gc = {}
                if os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
                        _gc = json.load(_f)
                _saved_goal = _gc.get("study_goal", 0)
                _saved_type = _gc.get("goal_type", "central")
                if _saved_goal > 0:
                    _stn = "集中培训" if _saved_type == "central" else "网络自学"
                    console.print(f"发现保存的学习目标: {_stn} {_saved_goal} 学时", style="green")
                    _use = await async_input("使用？(y/n)", default="y", timeout=5)
                    if _use in ('y', 'yes', ''):
                        learner.study_goal = _saved_goal
                        learner.goal_type = _saved_type
                if learner.study_goal <= 0:
                    console.print("目标类型: 集中培训(c) / 网络自学(w)？(默认c): ", style="yellow", end="")
                    _gt = input().strip().lower()
                    learner.goal_type = "online" if _gt in ('w', '网络自学') else "central"
                    console.print(f"设置学习目标学时数（0=不限制）: ", style="yellow", end="")
                    _gi = input().strip()
                    if _gi.replace('.', '').isdigit() and float(_gi) > 0:
                        learner.study_goal = float(_gi)
                        _gc["study_goal"] = learner.study_goal
                        _gc["goal_type"] = learner.goal_type
                        with open(CONFIG_PATH, "w", encoding="utf-8") as _f:
                            json.dump(_gc, _f, ensure_ascii=False, indent=2)
                        _tn = "集中培训" if learner.goal_type == "central" else "网络自学"
                        console.print(f"学习目标已保存: {_tn} {learner.study_goal} 学时", style="green")
                if learner.study_goal > 0:
                    console.print("查询当前培训学时...", style="blue")
                    _h = await learner._get_study_hours(learner.pages[0])
                    _tn = "集中培训" if learner.goal_type == "central" else "网络自学"
                    _cur = _h.get(learner.goal_type, 0)
                    console.print(f"当前{_tn}: {_cur:.1f}学时", style="bold blue")
                    console.print(f"目标: {learner.study_goal} 学时", style="bold blue")
                    if _cur >= learner.study_goal and _cur > 0:
                        console.print(f"当前{_tn}已训 {_cur:.1f} 学时，已达到目标 {learner.study_goal} 学时，无需学习！", style="bold green")
                        console.print("按回车键退出...", style="yellow")
                        input()
                        return
                    
            except Exception as _ge:
                debug(f"学习目标异常: {_ge}")
            

            # 选择学习模式（有目标时自动选择）
            if learner.study_goal > 0:
                _tn = "集中培训" if learner.goal_type == "central" else "网络自学"
                _mode = "1" if learner.goal_type == "central" else "2"
                console.print(f"目标类型为「{_tn}」，自动选择{'专题班模式' if _mode == '1' else '课程模式'}", style="blue")
            else:
                console.print()
                _mode = await async_input("选择模式: 专题班(1) / 课程列表(2)？(默认1)", default="1", timeout=5)
            if _mode == "2":
                await learner._course_mode(learner.pages[0])
                console.print("\n课程模式完成! 按回车键关闭浏览器...", style="yellow")
                input()
                return
            
            # 访问专题班页面
            page = learner.pages[0]
            await page.goto("https://u.ccb.com/workshop/#/index?collegeId=&departmentId=&orderby=praise")
            await asyncio.sleep(5)
            
            # 根据标签筛选
            if tags:
                # 通过命令行参数传入的标签
                learner.tags_to_learn = list(tags)
                await learner.filter_by_tags(page)
                await asyncio.sleep(3)
                # 保存CLI标签供下次使用
                try:
                    with open(TAGS_STATE_PATH, "w", encoding="utf-8") as _f:
                        json.dump({"tags": list(tags), "source": "cli"}, _f)
                except:
                    pass
            else:
                # 尝试加载保存的标签
                saved_tags = None
                if os.path.exists(TAGS_STATE_PATH):
                    try:
                        with open(TAGS_STATE_PATH, "r", encoding="utf-8") as _f:
                            _d = json.load(_f)
                            saved_tags = _d.get("tags", [])
                    except:
                        pass
                
                use_tags = []
                if saved_tags:
                    console.print(f"发现上次保存的筛选标签: {', '.join(saved_tags)}", style="green")
                    _c = await async_input("使用(u) / 重新选择(r) / 跳过(s)？(u/r/s，默认u)", default="u", timeout=5)
                    if _c in ('', 'u', 'use'):
                        use_tags = saved_tags
                    elif _c in ('r', 're', '重新'):
                        use_tags = await learner.interactive_tag_selection(page)
                
                if not use_tags and not saved_tags:
                    console.print("[blue]是否进行标签筛选？(y/n，默认n)[/blue]", end="")
                    _c = input().strip().lower()
                    if _c in ('y', 'yes'):
                        use_tags = await learner.interactive_tag_selection(page)
                
                if use_tags:
                    learner.tags_to_learn = use_tags
                    await learner.filter_by_tags(page)
                    await asyncio.sleep(3)
                    # 保存本次选择
                    try:
                        with open(TAGS_STATE_PATH, "w", encoding="utf-8") as _f:
                            json.dump({"tags": use_tags}, _f, ensure_ascii=False, indent=2)
                        console.print("标签选择已保存，下次可直接使用", style="green")
                    except:
                        pass
                else:
                    # 删除保存的标签（如果用户跳过了）
                    if os.path.exists(TAGS_STATE_PATH):
                        try:
                            os.remove(TAGS_STATE_PATH)
                        except:
                            pass
            
            # 获取当前页的专题班
            page_num = 1
            current_workshops = await learner.get_workshops(page)
            
            while current_workshops:
                console.print(f"第 {page_num} 页，共 {len(current_workshops)} 个专题班", style="green")
                await learner.display_workshops(current_workshops)
                
                if page_num == 0:  # 只在第一页问
                    console.print("从第一个专题班开始按顺序学习，按回车键开始（或输入编号 n 跳过前面 n 个）: ", style="yellow", end="")
                    skip_str = input().strip()
                    skip = 0
                    if skip_str.isdigit():
                        skip = int(skip_str)
                    elif skip_str:
                        skip = int(skip_str)
                else:
                    skip = 0
                
                for idx in range(skip, len(current_workshops)):
                    ws = current_workshops[idx]
                    console.print(f"\n[{idx+1}/{len(current_workshops)}] 开始学习: {ws['title'][:50]}", style="bold blue")
                    
                    try:
                        success, wpage = await learner.enroll_workshop(page, ws['title'])
                        if success:
                            await learner.find_and_learn_courses(wpage, 0)
                        else:
                            console.print(f"进入专题班失败，跳过", style="red")
                    except Exception as e:
                        console.print(f"学习过程出错: {e}", style="red")
                        import traceback
                        traceback.print_exc()
                    
                    # 返回专题班列表页，准备下一个
                    try:
                        await page.goto("https://u.ccb.com/workshop/#/index",
                                        wait_until="networkidle", timeout=15000)
                        await page.wait_for_timeout(3000)
                    except:
                        pass
                    
                    # 每个专题班之间暂停，让用户确认
                    if idx < len(current_workshops) - 1:
                        c = await async_input("\n是否继续学习下一个专题班？(y/n，默认y)", default="y", timeout=5)
                        if c in ('n', 'no'):
                            console.print("跳过剩余专题班", style="yellow")
                            break
                
                # 当前页学完，看是否有下一页
                console.print(f"\n当前页({page_num})已全部学完", style="green")
                has_next = await learner.go_to_next_page(page)
                if not has_next:
                    console.print("已到最后一页，学习完成!", style="bold green")
                    break
                
                page_num += 1
                console.print(f"\n进入第 {page_num} 页", style="blue")
                await page.wait_for_timeout(3000)
                current_workshops = await learner.get_workshops(page)
            
            if not current_workshops and page_num == 1:
                console.print("未找到专题班", style="yellow")
            
            console.print("\n✓ 学习流程完成! 浏览器将保持打开", style="bold green")
            console.print("按回车键关闭浏览器...", style="yellow")
            input("")
            
        finally:
            await learner.close()
    
    asyncio.run(run())


@cli.command()
def hours():
    """查看当前学时"""
    async def run():
        learner = CCBULearner(headless=False)
        try:
            await learner.init()
            await learner.login()
            hours = await learner.get_study_hours()
            console.print("\n按回车键关闭浏览器...", style="yellow")
            input("")
        finally:
            await learner.close()
    
    asyncio.run(run())


@cli.command()
def clear():
    """清除所有保存的会话、凭证和标签筛选"""
    removed = []
    for _p in [STORAGE_STATE_PATH, USER_CREDENTIALS_PATH, TAGS_STATE_PATH, CONFIG_PATH]:
        if os.path.exists(_p):
            try:
                os.remove(_p)
                removed.append(_p)
            except:
                pass
    if removed:
        for _r in removed:
            console.print(f"已删除: {_r}", style="green")
        console.print("✓ 清除完成", style="bold green")
    else:
        console.print("没有需要清除的文件", style="yellow")


if __name__ == "__main__":
    cli()
