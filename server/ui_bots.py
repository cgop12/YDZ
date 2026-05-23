"""
打字对战 - GUI 自动化测试机器人
===================================

特点：
  - 启动**真实的客户端 GUI 窗口**（不是黑窗口）
  - 自动输入名字登录（通过 --name 参数，客户端自动加入）
  - 自动识别比赛题目并**模拟人类打字**（通过 pywinauto 控制 GUI）

使用方法：
  py server/ui_bots.py [机器人数量] [主机] [端口]

示例：
  py server/ui_bots.py 3                # 启动3个机器人，连接 127.0.0.1:8888
  py server/ui_bots.py 2 192.168.1.100 8888
"""

import subprocess
import time
import random
import os
import sys
import json
import threading

# ─────────────────────────────────────────────────────────────
# 依赖检查
# ─────────────────────────────────────────────────────────────
try:
    from pywinauto import Application
    from pywinauto import timings
    timings.TypingAttack = 0.01  # 修复：正确的属性名
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────
CLIENT_PATHS = [
    r"D:\ydz\client\dist\YDZClient.exe",
    r"D:\ydz\client\YDZClient.exe",
    r"D:\ydz\YDZClient.exe",
]

HOST = "127.0.0.1"
PORT = 8888
DEFAULT_BOT_COUNT = 2

# 打字配置（人类模拟）
TYPING_DELAY_MIN = 0.04
TYPING_DELAY_MAX = 0.12
ERROR_RATE = 0.05           # 5% 概率打错
HESITATE_CHANCE = 0.1       # 10% 概率犹豫
HESITATE_TIME = (0.1, 0.3)  # 犹豫时长范围
START_DELAY = (1, 3)        # 倒计时结束后延迟开始打字范围
COMPLETION_MIN = 0.55        # 最少完成 55%
COMPLETION_MAX = 0.95        # 最多完成 95%

# 名字库
SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
GIVENS = "明伟芳敏静洋涛昊爽悦强毅峰雪琳辉建国庆志文武杰磊鹏"

# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def log(msg: str, name: str = "SYSTEM"):
    """日志输出"""
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] [{name:10s}] {msg}")


def random_name() -> str:
    """生成随机中文名字"""
    return random.choice(SURNAMES) + random.choice(GIVENS) + random.choice(GIVENS)


def find_client() -> str:
    """查找客户端 EXE 路径"""
    for p in CLIENT_PATHS:
        if os.path.exists(p):
            return p
    return ""


# ─────────────────────────────────────────────────────────────
# GuiBot 类
# ─────────────────────────────────────────────────────────────

class GuiBot:
    """
    一个 GuiBot 对应：
      - 1 个真实的客户端 GUI 窗口
      - 1 个 WebSocket 连接（用于获取 match_begin 中的比赛文本）
    """

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 8888):
        self.name = name
        self.host = host
        self.port = port
        self.process = None           # subprocess.Popen
        self.app = None              # pywinauto Application
        self.window = None           # pywinauto Window
        self.match_text = ""         # 从 WebSocket 获取的比赛文本
        self.match_active = False    # 比赛是否进行中
        self.ws = None               # WebSocket 连接
        self._ws_thread = None      # WebSocket 监听线程
        self._typing_thread = None  # 打字线程

    # ── 启动 GUI 客户端 ──────────────────────────────────
    def start_gui(self) -> bool:
        """启动真实的客户端 GUI 窗口"""
        client_exe = find_client()
        if not client_exe:
            log(f"❌ 找不到客户端 EXE", self.name)
            return False

        log(f"正在启动 GUI 客户端...", self.name)
        try:
            self.process = subprocess.Popen(
                [
                    client_exe,
                    "--name", self.name,
                    "--host", self.host,
                    "--port", str(self.port),
                ],
                cwd=os.path.dirname(client_exe),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            log(f"✅ GUI 已启动 (PID={self.process.pid})", self.name)
            return True
        except Exception as e:
            log(f"❌ 启动失败: {e}", self.name)
            return False

    # ── 连接 pywinauto ────────────────────────────────────
    def connect_pywinauto(self, timeout: int = 30) -> bool:
        """
        通过进程 ID 连接 GUI 窗口（避免多开混淆）
        改进点：
          1. 使用 title_re 模糊匹配窗口标题
          2. 添加重试逻辑（每 2 秒重试一次）
          3. 验证窗口可访问性
          4. 备用方案：如果标题匹配失败，尝试 top_window()
        """
        if not PYWINAUTO_AVAILABLE:
            log(f"⚠️  pywinauto 未安装", self.name)
            return False

        if not self.process or not self.process.pid:
            log(f"❌ 进程未启动，无法连接", self.name)
            return False

        log(f"正在连接 GUI 窗口 (PID={self.process.pid})...", self.name)

        # 重试逻辑：每 2 秒尝试一次，直到超时
        start_time = time.time()
        last_error = None

        while time.time() - start_time < timeout:
            try:
                # 步骤1: 通过 PID 连接进程
                self.app = Application(backend="uia").connect(
                    process=self.process.pid,
                    timeout=2,  # 单次连接超时 2 秒
                )

                # 步骤2: 尝试多种方式找到窗口
                window_found = False

                # 方法A: 使用 title_re 模糊匹配
                try:
                    self.window = self.app.window(title_re=".*打字对战.*")
                    _ = self.window.wrapper_object()  # 验证窗口可访问
                    window_found = True
                    log(f"✅ 窗口已连接 (title_re 匹配)", self.name)
                except Exception:
                    pass  # 继续尝试其他方法

                # 方法B: 如果 title_re 失败，尝试 top_window()
                if not window_found:
                    try:
                        self.window = self.app.top_window()
                        _ = self.window.wrapper_object()
                        # 验证这个窗口确实是对战窗口（检查标题）
                        try:
                            title = self.window.window_text()
                            if "打字对战" in title:
                                window_found = True
                                log(f"✅ 窗口已连接 (top_window 匹配, 标题={title})", self.name)
                        except Exception:
                            pass
                    except Exception:
                        pass

                # 方法C: 枚举所有窗口，找到包含"打字对战"的
                if not window_found:
                    try:
                        windows = self.app.windows()
                        for w in windows:
                            try:
                                title = w.window_text()
                                if "打字对战" in title:
                                    self.window = w
                                    _ = self.window.wrapper_object()
                                    window_found = True
                                    log(f"✅ 窗口已连接 (枚举找到, 标题={title})", self.name)
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

                if window_found:
                    return True

                # 如果所有方法都失败，记录错误并重试
                last_error = "窗口未找到"
                log(f"⏳ 窗口尚未就绪，{timeout - int(time.time() - start_time)} 秒后重试...", self.name)
                time.sleep(2)

            except Exception as e:
                last_error = str(e)
                log(f"⏳ 连接失败，重试中... ({last_error[:50]})", self.name)
                time.sleep(2)

        # 超时退出
        log(f"❌ 连接窗口失败 (超时 {timeout} 秒): {last_error}", self.name)
        return False

    # ── WebSocket 监听（获取比赛文本）────────────────────
    def start_ws_listener(self):
        """启动 WebSocket 监听线程，获取 match_begin 中的比赛文本"""
        if not WEBSOCKETS_AVAILABLE:
            log(f"⚠️  websockets 未安装", self.name)
            return

        # WebSocket 使用不同名字，避免与 GUI 客户端冲突
        ws_name = f"{self.name}_bot"

        async def listen():
            uri = f"ws://{self.host}:{self.port}"
            try:
                async with websockets.connect(uri) as ws:
                    self.ws = ws
                    await ws.send(json.dumps({"type": "join", "name": ws_name}))
                    log(f"WebSocket 已连接 ({ws_name})", self.name)

                    async for raw in ws:
                        msg = json.loads(raw)
                        t = msg.get("type", "")

                        if t == "match_begin":
                            self.match_text = msg.get("text", "")
                            self.match_active = True
                            text_len = len(self.match_text)
                            log(f"🏁 比赛开始! 文本长度: {text_len} 字", self.name)
                            # 在新线程中开始打字（不阻塞 WebSocket 接收）
                            if self.window:
                                self._typing_thread = threading.Thread(
                                    target=self._type_in_gui, daemon=True
                                )
                                self._typing_thread.start()

                        elif t == "round_end":
                            self.match_active = False
                            log(f"🏅 本轮结束", self.name)

                        elif t == "final_ranking":
                            self.match_active = False
                            log(f"🏆 全部比赛结束", self.name)

                        elif t == "error":
                            log(f"⚠️  服务器错误: {msg.get('message', '')}", self.name)

            except Exception as e:
                log(f"⚠️  WebSocket 错误: {e}", self.name)

        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(listen())

        self._ws_thread = threading.Thread(target=run_loop, daemon=True)
        self._ws_thread.start()

    # ── 在 GUI 中打字 ────────────────────────────────────
    def _type_in_gui(self):
        """在 GUI 窗口的输入框中模拟人类打字"""
        if not self.match_text:
            log(f"❌ 没有比赛文本，无法打字", self.name)
            return

        if not self.window:
            log(f"❌ 没有连接到 GUI 窗口", self.name)
            return

        # 等待倒计时结束 + 人类延迟
        delay = random.uniform(*START_DELAY)
        log(f"⏳ 等待 {delay:.1f} 秒后开始打字...", self.name)
        time.sleep(delay)

        # ── 查找输入框（多种方式）────────────────────────
        input_box = None
        find_methods = [
            # 方法1: 通过 control_type（标准方式）
            lambda: self.window.child_window(control_type="Edit"),
            # 方法2: 通过类名
            lambda: self.window.child_window(class_name="QLineEdit"),
            # 方法3: 枚举所有 Edit 控件
            lambda: self._find_edit_by_enumeration(),
        ]

        for i, method in enumerate(find_methods):
            try:
                input_box = method()
                if input_box:
                    _ = input_box.wrapper_object()  # 验证可访问
                    log(f"✅ 输入框已找到 (方法{i+1})", self.name)
                    break
            except Exception as e:
                log(f"⚠️  方法{i+1} 失败: {str(e)[:50]}", self.name)
                continue

        if not input_box:
            log(f"❌ 找不到输入框，尝试打印控件结构...", self.name)
            try:
                self.window.print_control_identifiers()
            except Exception:
                pass
            return

        # ── 激活窗口并聚焦输入框 ────────────────────────
        try:
            self.window.set_focus()
            time.sleep(0.3)
            input_box.set_focus()
            input_box.click_input()  # 使用 click_input 而不是 click
            time.sleep(0.2)
            # 清空输入框
            input_box.set_edit_text("")
            time.sleep(0.1)
            log(f"✅ 输入框已激活，开始打字", self.name)
        except Exception as e:
            log(f"⚠️  聚焦输入框时出现问题: {e}", self.name)

        # 人类模拟打字参数
        target_pct = random.uniform(COMPLETION_MIN, COMPLETION_MAX)
        target_len = int(len(self.match_text) * target_pct)
        errors = 0

        log(f"📝 目标: {target_len}/{len(self.match_text)} 字 ({target_pct*100:.0f}%)", self.name)

        # 逐字打字
        for i in range(target_len):
            if not self.match_active:
                log(f"⏹️  比赛已结束，停止打字", self.name)
                break

            char = self.match_text[i]

            # 偶尔打错（输入一个错误字符，然后删除）
            if random.random() < ERROR_RATE and ord(char) > 128:
                wrong_char = chr(ord(char) + random.choice([-2, -1, 1, 2]))
                try:
                    input_box.type_keys(wrong_char, with_spaces=True, pause=0.01)
                    time.sleep(0.05)
                    input_box.type_keys("{BACKSPACE}", with_spaces=True, pause=0.01)
                    errors += 1
                except Exception:
                    pass

            # 输入正确字符
            try:
                input_box.type_keys(char, with_spaces=True, pause=0.01)
            except Exception:
                pass

            # 按键间延迟（模拟人类变速）
            delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)

            # 偶尔犹豫（模拟"思考"）
            if random.random() < HESITATE_CHANCE:
                delay += random.uniform(*HESITATE_TIME)

            time.sleep(delay)

        log(f"✅ 打字完成! (错误: {errors} 个)", self.name)

    def _find_edit_by_enumeration(self):
        """
        通过枚举所有子控件来查找 Edit 控件
        作为备用方案，当 child_window 找不到时使用
        """
        try:
            # 获取窗口的所有后代元素
            descendants = self.window.descendants()
            for elem in descendants:
                try:
                    if elem.control_type() == "Edit":
                        return elem
                except Exception:
                    continue
        except Exception as e:
            log(f"⚠️  枚举控件失败: {e}", self.name)
        return None

    # ── 停止并清理 ────────────────────────────────────────
    def stop(self):
        """停止机器人并清理进程"""
        self.match_active = False
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except Exception:
                    self.process.kill()
                log(f"已关闭", self.name)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────

def main():
    # 解析命令行参数
    bot_count = DEFAULT_BOT_COUNT
    host = HOST
    port = PORT

    if len(sys.argv) > 1:
        try:
            bot_count = int(sys.argv[1])
        except ValueError:
            pass

    if len(sys.argv) > 2:
        host = sys.argv[2]

    if len(sys.argv) > 3:
        try:
            port = int(sys.argv[3])
        except ValueError:
            pass

    print()
    print("=" * 62)
    print(" " * 15 + "打字对战 - GUI 自动化测试机器人")
    print("=" * 62)
    print()

    # 1. 查找客户端 EXE
    log("正在查找客户端 EXE...")
    client_exe = find_client()
    if not client_exe:
        log("❌ 找不到 YDZClient.exe！")
        log("   请确保以下路径之一存在：")
        for p in CLIENT_PATHS:
            log(f"   - {p}")
        log("   或先运行 client/build_client.bat 编译客户端")
        return
    log(f"✅ 找到客户端: {client_exe}")

    # 2. 检查依赖
    print()
    if not PYWINAUTO_AVAILABLE:
        log("⚠️  pywinauto 未安装，正在尝试安装...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pywinauto"],
                check=True,
            )
            log("✅ pywinauto 安装成功，请重新运行脚本")
        except Exception as e:
            log(f"❌ 无法安装 pywinauto: {e}")
        return

    if not WEBSOCKETS_AVAILABLE:
        log("⚠️  websockets 未安装，正在尝试安装...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "websockets"],
                check=True,
            )
            log("✅ websockets 安装成功，请重新运行脚本")
        except Exception as e:
            log(f"❌ 无法安装 websockets: {e}")
        return

    log("✅ 所有依赖已就绪")

    # 3. 生成名字并启动 GUI 客户端
    print()
    names = [random_name() for _ in range(bot_count)]
    log(f"🎮 机器人选手: {', '.join(names)}")
    log(f"🖥️  服务器: {host}:{port}")

    bots = []
    for i, name in enumerate(names):
        log(f"正在启动第 {i+1}/{bot_count} 个机器人: {name}")
        bot = GuiBot(name, host, port)
        if bot.start_gui():
            bots.append(bot)
            log(f"✅ {name} GUI 已启动 (PID={bot.process.pid})")
        else:
            log(f"❌ {name} 启动失败")

        # 错开启动，避免窗口重叠 + 给系统时间创建窗口
        if i < len(names) - 1:  # 最后一个不需要等待
            log(f"⏳ 等待 2 秒后启动下一个...")
            time.sleep(2)

    if len(bots) == 0:
        log("❌ 没有成功启动任何客户端")
        return

    log(f"✅ 已启动 {len(bots)} 个 GUI 窗口，开始连接...")

    # 4. 连接 pywinauto 到每个窗口
    # 注意：connect_pywinauto() 内部已有重试逻辑（最多等 30 秒）
    print()
    log("🔗 正在连接 GUI 窗口 (pywinauto)...")
    connected_bots = []
    for i, bot in enumerate(bots):
        log(f"连接 {i+1}/{len(bots)}: {bot.name}...")
        if bot.connect_pywinauto(timeout=30):
            connected_bots.append(bot)
            # 可选：打印窗口控件结构（调试用）
            # bot.window.print_control_identifiers()
        time.sleep(0.5)

    if len(connected_bots) == 0:
        log("⚠️  没有成功连接任何窗口，打字功能将不可用")
        log("   提示: 请检查客户端是否正常启动，或查看日志")
    else:
        log(f"✅ 已连接 {len(connected_bots)}/{len(bots)} 个窗口")

    if len(connected_bots) == 0:
        log("⚠️  没有成功连接任何窗口，打字功能将不可用")
    else:
        log(f"✅ 已连接 {len(connected_bots)} 个窗口")

    # 6. 启动 WebSocket 监听（获取比赛文本）
    print()
    log("📡 正在启动 WebSocket 监听...")
    for bot in connected_bots:
        bot.start_ws_listener()
        time.sleep(0.5)

    # 7. 提示用户操作
    print()
    print("=" * 62)
    print("  🎯 操作步骤：")
    print()
    print("  1️⃣  确保服务端已启动（运行 server/main.py 或 YDZServer.exe）")
    print("  2️⃣  在服务端界面点击『▶ 开始比赛』")
    print("  3️⃣  等待倒计时结束，机器人将自动开始打字")
    print()
    print("  💡 提示: 机器人会模拟人类行为（变速、偶尔打错、不完全打完）")
    print()
    print("  按 Ctrl+C 退出并关闭所有窗口")
    print("=" * 62)
    print()

    # 8. 保持主线程运行，等待用户中断
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        log("收到中断信号，正在清理...")

    # 9. 清理所有机器人进程
    print()
    log("🗑️  正在关闭所有机器人窗口...")
    for bot in bots:
        bot.stop()

    # 额外清理可能残留的进程
    print()
    log("🧹 清理残留进程...")
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            if p.info['name'] and 'YDZClient' in p.info['name']:
                try:
                    p.kill()
                    log(f"已终止残留进程: PID={p.pid}")
                except Exception:
                    pass
    except Exception:
        pass

    print()
    log("✅ 全部清理完成，再见！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断")
        # 尝试清理所有残留的 YDZClient 进程
        try:
            import psutil
            for p in psutil.process_iter(['name']):
                if p.info['name'] and 'YDZClient' in p.info['name']:
                    try:
                        p.kill()
                    except Exception:
                        pass
        except Exception:
            pass
        print("✅ 已退出")
    except Exception as e:
        log(f"❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
