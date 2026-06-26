# 建行大学自动学习工具

## 功能说明

1. **用户登录**：支持自动登录（在CLI输入用户名密码）或手动登录
2. **专题班学习**：自动进行专题班的学习，展示专题班进度、课程进度
3. **标签筛选**：可以指定只学习带有特定标签的专题班
4. **学时统计**：读取并记录用户的学习学时
5. **目标学时**：可以指定本次学习的学时目标，达到后自动停止
6. **多页面学习**：支持同时开启多个页面进行学习
7. **后台学习**：支持隐藏浏览器界面进行后台学习

## 安装步骤

### Mac / Linux（推荐）

```bash
git clone <仓库地址>
cd CCBU-Auto
./setup.sh
```

### 手动安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用方法

### 基本命令

#### 开始学习

```bash
python main.py start
```

#### 查看当前学时

```bash
python main.py hours
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--headless` | 隐藏浏览器界面（后台学习） | 否 |
| `--workers` | 同时学习的页面数量 | 1 |
| `--target-hours` | 目标学习学时，0表示不限制 | 0 |
| `--tags` | 要学习的标签，可多次指定 | 无 |

### 使用示例

1. **基础学习（显示浏览器，1个页面，无学时限制）**：
   ```bash
   python main.py start
   ```

2. **后台学习（隐藏浏览器）**：
   ```bash
   python main.py start --headless
   ```

3. **同时开启3个页面学习**：
   ```bash
   python main.py start --workers 3
   ```

4. **学习2个学时后自动停止**：
   ```bash
   python main.py start --target-hours 2
   ```

5. **只学习带有"党的创新理论教育"标签的内容**：
   ```bash
   python main.py start --tags "党的创新理论教育"
   ```

6. **组合使用多个参数**：
   ```bash
   python main.py start --headless --workers 2 --target-hours 1.5 --tags "党的创新理论教育" --tags "党性教育"
   ```

## 学习记录

学习记录会保存在 `study_records.json` 文件中，记录每次学习的时间和累计学时。

## 注意事项

1. 可以选择自动登录（输入用户名密码）或手动登录
2. 登录成功后按回车键继续
3. 请确保网络连接稳定
4. 使用多页面学习时请注意系统资源使用情况

## 登录方式

程序提供两种登录方式：

1. **自动登录**：在CLI中输入建行统一认证账号和密码，程序会自动填写并登录
2. **手动登录**：在浏览器中手动完成登录操作，登录成功后按回车键继续
