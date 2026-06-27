#!/usr/bin/env python3
"""CCBU-Auto Textual TUI Application"""
import asyncio
import json
import os
import sys
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Header,
    Input,
    Label,
    ProgressBar,
    RadioSet,
    RadioButton,
    RichLog,
    Static,
    Switch,
    Checkbox,
)

# Import CCBULearner from main.py
from main import CCBULearner, CONFIG_PATH, PROGRESS_PATH, STORAGE_STATE_PATH

# ─── Messages (worker → UI) ────────────────────────────────────────


class LogMsg(Message):
    def __init__(self, text: str, style: str = ""):
        super().__init__()
        self.text = text
        self.style = style


class ProgressMsg(Message):
    """Worker progress update."""
    def __init__(self, data: dict):
        super().__init__()
        self.data = data


class HoursMsg(Message):
    """Study hours update."""
    def __init__(self, data: dict):
        super().__init__()
        self.data = data


class DoneMsg(Message):
    """Learning finished."""
    def __init__(self, success: int, failed: int):
        super().__init__()
        self.success = success
        self.failed = failed


class LoginStatusMsg(Message):
    def __init__(self, text: str):
        super().__init__()
        self.text = text


class LoginDoneMsg(Message):
    def __init__(self, success: bool, username: str = ""):
        super().__init__()
        self.success = success
        self.username = username


# ─── Config Screen ─────────────────────────────────────────────────


class ConfigScreen(Screen):
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        # Load saved config
        saved = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
            except:
                pass

        self._saved = saved
        default_workers = str(saved.get("workers", 1))
        default_headless = saved.get("headless", False)

        with Container(id="config-container"):
            yield Static("运行配置", classes="title")
            with Horizontal(classes="config-row"):
                yield Label("工作线程数:")
                yield Input(value=default_workers, id="input-workers")
            with Horizontal(classes="config-row"):
                yield Label("无头模式:")
                yield Switch(value=default_headless, id="switch-headless")
            yield Button("开始", variant="primary", id="btn-start")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-start":
            workers_input = self.query_one("#input-workers", Input)
            headless_switch = self.query_one("#switch-headless", Switch)

            try:
                workers = int(workers_input.value)
                if workers < 1:
                    workers = 1
            except ValueError:
                workers = 1

            headless = headless_switch.value

            # Save config
            try:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump({"workers": workers, "headless": headless}, f, ensure_ascii=False, indent=2)
            except:
                pass

            # Store in app
            self.app.cfg_workers = workers
            self.app.cfg_headless = headless
            self.app.switch_screen("login")


# ─── Login Screen ──────────────────────────────────────────────────


class LoginScreen(Screen):
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        # Load saved credentials
        creds = {}
        creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccbu_credentials.json")
        if os.path.exists(creds_path):
            try:
                with open(creds_path, "r", encoding="utf-8") as f:
                    creds = json.load(f)
            except:
                pass

        self._creds = creds
        saved_user = creds.get("username", "")
        saved_pass = creds.get("password", "")

        with Container(id="login-container"):
            yield Static("用户登录", classes="title")
            with Horizontal(classes="login-row"):
                yield Label("账号:")
                yield Input(value=saved_user, id="input-username")
            with Horizontal(classes="login-row"):
                yield Label("密码:")
                yield Input(value=saved_pass, password=True, id="input-password")
            yield Static("正在等待登录...", id="login-status")
            with Horizontal(classes="login-row"):
                yield RadioButton("自动登录", value=True, id="radio-auto")
                yield RadioButton("手动登录", value=False, id="radio-manual")
            yield Button("登录", variant="primary", id="btn-login")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-login":
            username = self.query_one("#input-username", Input).value
            password = self.query_one("#input-password", Input).value
            auto = self.query_one("#radio-auto", RadioButton).value

            if not username:
                self.query_one("#login-status", Static).update("[red]请输入账号[/red]")
                return

            self.app.cfg_username = username
            self.app.cfg_password = password
            self.app.cfg_auto_login = auto

            # Save credentials
            creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccbu_credentials.json")
            try:
                with open(creds_path, "w", encoding="utf-8") as f:
                    json.dump({"username": username, "password": password}, f, ensure_ascii=False, indent=2)
            except:
                pass

            self.app.switch_screen("goal")

    def on_mount(self):
        self.query_one("#input-password", Input).focus()


# ─── Goal Screen ───────────────────────────────────────────────────


class GoalScreen(Screen):
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        # Load saved goal
        goal_cfg = {}
        goal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccbu_config.json")
        if os.path.exists(goal_path):
            try:
                with open(goal_path, "r", encoding="utf-8") as f:
                    goal_cfg = json.load(f)
            except:
                pass

        saved_goal = goal_cfg.get("study_goal", 0)
        saved_type = goal_cfg.get("goal_type", "central")

        with Container(id="goal-container"):
            yield Static("学习目标", classes="title")
            with Horizontal(classes="goal-row"):
                yield Label("目标类型:")
                with RadioSet(id="radio-goal-type"):
                    yield RadioButton("集中培训", value=(saved_type == "central"), id="radio-central")
                    yield RadioButton("网络自学", value=(saved_type == "online"), id="radio-online")
            with Horizontal(classes="goal-row"):
                yield Label("目标学时:")
                yield Input(value=str(saved_goal), id="input-goal-hours")
            yield Button("继续", variant="primary", id="btn-goal")
            yield Button("跳过（不限制）", id="btn-skip-goal")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-goal":
            radio = self.query_one("#radio-goal-type", RadioSet)
            # Get selected radio button
            goal_type = "central"
            for rb in radio.query(RadioButton):
                if rb.value:
                    goal_type = "central" if rb.id == "radio-central" else "online"
                    break

            try:
                hours = float(self.query_one("#input-goal-hours", Input).value)
            except ValueError:
                hours = 0

            self.app.cfg_goal_type = goal_type
            self.app.cfg_goal_hours = hours
            self._save_goal(goal_type, hours)
            self.app.switch_screen("tag")

        elif event.button.id == "btn-skip-goal":
            self.app.cfg_goal_type = "central"
            self.app.cfg_goal_hours = 0
            self._save_goal("central", 0)
            self.app.switch_screen("tag")

    def _save_goal(self, goal_type, hours):
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccbu_config.json")
        try:
            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["study_goal"] = hours
            cfg["goal_type"] = goal_type
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except:
            pass


# ─── Tag Screen ────────────────────────────────────────────────────


class TagScreen(Screen):
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        with Container(id="tag-container"):
            yield Static("选择标签（可多选）", classes="title")
            yield Vertical(id="tag-list")
            with Horizontal(id="tag-buttons"):
                yield Button("跳过", id="btn-skip-tags")
                yield Button("确认选择", variant="primary", id="btn-confirm-tags")

    def on_mount(self):
        # Tags will be populated after login when the browser has the tag list
        # For now, show a placeholder
        tag_list = self.query_one("#tag-list", Vertical)
        tag_list.mount(Static("标签将在浏览器加载后显示..."))

    def set_tags(self, tags_by_category: dict):
        """Called after login to populate tags."""
        tag_list = self.query_one("#tag-list", Vertical)
        tag_list.remove_children()

        self._all_tags = []
        for category, tags in tags_by_category.items():
            tag_list.mount(Static(f"[bold cyan]{category}[/bold cyan]"))
            for tag in tags:
                self._all_tags.append((category, tag))
                cb = Checkbox(f"{tag}", value=False, classes="tag-cb")
                tag_list.mount(cb)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-skip-tags":
            self.app.cfg_tags = []
            self.app.switch_screen("dashboard")
        elif event.button.id == "btn-confirm-tags":
            selected = []
            for cb in self.query(".tag-cb"):
                if cb.value:
                    selected.append(str(cb.label))
            self.app.cfg_tags = selected
            self.app.switch_screen("dashboard")


# ─── Dashboard Screen ──────────────────────────────────────────────


class DashboardScreen(Screen):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("q", "quit", "退出"),
    ]

    # Reactive state
    central_hours: reactive[float] = reactive(0.0)
    online_hours: reactive[float] = reactive(0.0)
    completed_count: reactive[int] = reactive(0)
    total_count: reactive[int] = reactive(0)
    failed_count: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        with Vertical(id="dashboard"):
            yield Header()
            with Container(id="top-bar"):
                yield Static("CCBU-Auto 自动学习", id="top-title")
                yield Static("", id="top-status")

            with Container(id="main-area"):
                with Vertical(id="left-panel"):
                    with Container(id="hours-box"):
                        yield Static("[bold]培训学时[/bold]")
                        yield Static("集中培训: -- 学时", id="lbl-central")
                        yield Static("网络自学: -- 学时", id="lbl-online")
                        yield Static("更新时间: --", id="lbl-hours-time")

                    with Container(id="goal-box"):
                        yield Static("[bold]学习目标[/bold]")
                        yield Static("--", id="lbl-goal-info")
                        yield ProgressBar(total=100, id="goal-progress")

                with Vertical(id="right-panel"):
                    yield Static("学习进度", id="progress-header")
                    yield DataTable(id="worker-table")

            with Container(id="log-panel"):
                yield Static("日志", classes="label")
                yield RichLog(id="log-view", markup=True)

    def on_mount(self):
        # Setup worker table
        table = self.query_one("#worker-table", DataTable)
        table.add_columns("线程", "课程", "进度", "预计", "状态")
        table.cursor_type = "none"

        # Set goal info
        goal_type = getattr(self.app, "cfg_goal_type", "central")
        goal_hours = getattr(self.app, "cfg_goal_hours", 0)
        type_name = "集中培训" if goal_type == "central" else "网络自学"
        if goal_hours > 0:
            self.query_one("#lbl-goal-info").update(f"{type_name} {goal_hours:.0f} 学时")
        else:
            self.query_one("#lbl-goal-info").update("不限制")

        # Start the learning process
        self.run_worker(self._run_learning, thread=True)

    async def _run_learning(self):
        """Main learning worker - runs in background thread."""
        app = self.app
        cfg_workers = getattr(app, "cfg_workers", 1)
        cfg_headless = getattr(app, "cfg_headless", False)
        cfg_username = getattr(app, "cfg_username", "")
        cfg_password = getattr(app, "cfg_password", "")
        cfg_auto_login = getattr(app, "cfg_auto_login", True)
        cfg_goal_type = getattr(app, "cfg_goal_type", "central")
        cfg_goal_hours = getattr(app, "cfg_goal_hours", 0)
        cfg_tags = getattr(app, "cfg_tags", [])

        # Create callbacks
        def log(msg, style=""):
            app.post_message(LogMsg(msg, style))

        def update_progress(data):
            app.post_message(ProgressMsg(data))

        def update_hours(data):
            app.post_message(HoursMsg(data))

        try:
            # Init learner
            log("正在初始化浏览器...")
            learner = CCBULearner(headless=cfg_headless, workers=cfg_workers)
            await learner.init()
            log("浏览器初始化完成", "green")

            # Login
            log("正在登录...")
            try:
                await learner.login(
                    page=learner.pages[0],
                    username=cfg_username,
                    password=cfg_password,
                    auto_login=cfg_auto_login,
                    log_callback=log,
                )
            except Exception as e:
                log(f"登录失败: {e}", "red")
                return
            log("登录成功", "green")

            # Set goal
            learner.study_goal = cfg_goal_hours
            learner.goal_type = cfg_goal_type

            # Set tags
            if cfg_tags:
                learner.tags_to_learn = cfg_tags

            # Navigate to workshop page
            page = learner.pages[0]
            await page.goto(
                "https://u.ccb.com/workshop/#/index?collegeId=&departmentId=&orderby=praise",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(5000)

            # Apply tag filter
            if cfg_tags:
                await learner.filter_by_tags(page)

            # Load progress
            progress = learner.load_progress()
            completed_ids = set(progress.get("completed_ws_ids", []))

            # Main collection + learning loop
            page_num = 1
            no_more_pages = False
            tasks = []
            ws_locks = {}

            while len(tasks) < cfg_workers and not no_more_pages:
                workshops = await learner.get_workshops(page)
                if not workshops:
                    no_more_pages = True
                    break

                log(f"第 {page_num} 页: {len(workshops)} 个专题班", "blue")

                new_tasks, new_locks = await learner._collect_workshops_courses(
                    page, workshops, completed_ids
                )
                tasks.extend(new_tasks)
                ws_locks.update(new_locks)

                if len(tasks) >= cfg_workers:
                    break

                moved = await learner.go_to_next_page(page)
                if not moved:
                    no_more_pages = True
                else:
                    page_num += 1
                    await page.wait_for_timeout(3000)

            if tasks:
                log(f"开始学习（{len(tasks)} 门课程, {cfg_workers} 个线程）", "bold blue")

                # Define fetch_more callback
                _fetch_lock = asyncio.Lock()
                _page_ref = [page]

                async def fetch_more_courses(queue):
                    if no_more_pages:
                        return 0
                    async with _fetch_lock:
                        if no_more_pages:
                            return 0
                        if cfg_goal_hours > 0:
                            try:
                                _h = await learner._get_study_hours(_page_ref[0])
                                _cur = _h.get(cfg_goal_type, 0)
                                if _cur >= cfg_goal_hours:
                                    log("已达到学习目标!", "bold green")
                                    return 0
                            except:
                                pass
                        moved = await learner.go_to_next_page(_page_ref[0])
                        if not moved:
                            return 0
                        nonlocal page_num
                        page_num += 1
                        await _page_ref[0].wait_for_timeout(3000)
                        new_ws = await learner.get_workshops(_page_ref[0])
                        if not new_ws:
                            return 0
                        log(f"自动翻到第 {page_num} 页: {len(new_ws)} 个专题班", "blue")
                        new_t, new_l = await learner._collect_workshops_courses(
                            _page_ref[0], new_ws, completed_ids
                        )
                        ws_locks.update(new_l)
                        for t in new_t:
                            queue.put_nowait((*t, 0))
                        if new_t:
                            log(f"新增 {len(new_t)} 门课程", "green")
                        return len(new_t)

                # Run parallel learning
                await learner.parallel_learn_courses(
                    tasks, ws_locks, fetch_more_courses, update_progress, update_hours, log
                )
            else:
                log("没有需要学习的课程", "yellow")

            app.post_message(DoneMsg(0, 0))

        except Exception as e:
            log(f"错误: {e}", "red")
            import traceback
            log(traceback.format_exc(), "red")
            app.post_message(DoneMsg(0, 0))

    # ── Message handlers ──

    def on_log_msg(self, msg: LogMsg):
        log_view = self.query_one("#log-view", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        style = msg.style or ""
        if "red" in style:
            log_view.write(f"[dim][{ts}][/dim] [red]{msg.text}[/red]")
        elif "green" in style:
            log_view.write(f"[dim][{ts}][/dim] [green]{msg.text}[/green]")
        elif "bold blue" in style:
            log_view.write(f"[dim][{ts}][/dim] [bold blue]{msg.text}[/bold blue]")
        elif "blue" in style:
            log_view.write(f"[dim][{ts}][/dim] [blue]{msg.text}[/blue]")
        elif "yellow" in style:
            log_view.write(f"[dim][{ts}][/dim] [yellow]{msg.text}[/yellow]")
        else:
            log_view.write(f"[dim][{ts}][/dim] {msg.text}")

    def on_progress_msg(self, msg: ProgressMsg):
        data = msg.data
        table = self.query_one("#worker-table", DataTable)
        wid = data.get("wid", 0)

        # Ensure enough rows
        while table.row_count <= wid:
            table.add_row(str(table.row_count + 1), "-", "-", "-", "等待中")

        course = data.get("course", "-")[:36]
        progress = data.get("progress", "-")
        eta = data.get("eta", "-")
        status = data.get("status", "-")

        table.update_cell(str(wid + 1), "课程", course)
        table.update_cell(str(wid + 1), "进度", progress)
        table.update_cell(str(wid + 1), "预计", eta)
        table.update_cell(str(wid + 1), "状态", status)

    def on_hours_msg(self, msg: HoursMsg):
        h = msg.data
        self.query_one("#lbl-central").update(f"集中培训: {h.get('central', 0):.1f} 学时")
        self.query_one("#lbl-online").update(f"网络自学: {h.get('online', 0):.1f} 学时")
        self.query_one("#lbl-hours-time").update(f"更新时间: {h.get('updated', '--')}")

        goal_type = getattr(self.app, "cfg_goal_type", "central")
        goal_hours = getattr(self.app, "cfg_goal_hours", 0)
        if goal_hours > 0:
            cur = h.get(goal_type, 0)
            pct = min(100, cur / goal_hours * 100)
            self.query_one("#goal-progress", ProgressBar).progress = pct
            type_name = "集中培训" if goal_type == "central" else "网络自学"
            self.query_one("#lbl-goal-info").update(
                f"{type_name} {cur:.1f}/{goal_hours:.0f} 学时 ({pct:.1f}%)"
            )

    def on_done_msg(self, msg: DoneMsg):
        self.query_one("#top-status").update(
            f"[bold green]完成: 成功 {msg.success}, 失败 {msg.failed}[/bold green]"
        )

    def action_quit(self):
        self.app.exit()


# ─── Main App ──────────────────────────────────────────────────────


class CCBUApp(App):
    TITLE = "CCBU-Auto 自动学习"
    CSS_PATH = "app.tcss"

    SCREENS = {
        "config": ConfigScreen,
        "login": LoginScreen,
        "goal": GoalScreen,
        "tag": TagScreen,
        "dashboard": DashboardScreen,
    }

    def on_mount(self):
        self.push_screen("config")


def main():
    CCBUApp().run()


if __name__ == "__main__":
    main()
