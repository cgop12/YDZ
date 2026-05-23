"""
打字对战 - GUI 自动化测试机器人 v2
===================================

改进点：
  - 放弃 pywinauto 控件识别（PyQt6 不兼容）
  - 使用 Windows API (SendMessage) 直接发送键盘消息
  - 使用窗口句柄 + SetForegroundWindow 聚焦窗口
  - 依赖客户端自动聚焦输入框的特性

使用方法：
  py server/ui_bots_v2.py [机器人数量] [主机] [端口]

依赖：
  - pywin32 (用于 Windows API)
  - websockets (用于获取比赛文本)

安装：
  pip install pywin32 websockets
"""

import subprocess
import time
import random
import os
import sys
import json
import threading
import ctypes
import ctypes.wintypes

# ─────────────────────────────────────────────────────────────
# Windows API 定义
# ─────────────────────────────────────────────────────────────
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 常量
WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_BACK = 0x08
VK_RETURN = 0x0D

# ─────────────────────────────────────────────────────────────
# 依赖检查
# ─────────────────────────────────────────────────────────────
try:
    import win32gui
    import win32process
    import win32con
    WIN32GUI_AVAILABLE = True
except ImportError:
    WIN32GUI_AVAILABLE = False

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

def find_window_by_pid(pid: int) -> int:
    """
    通过进程 ID 查找窗口句柄
    返回窗口句柄 (HWND)，如果找不到返回 0
    """
    if not WIN32GUI_AVAILABLE:
        return 0
    
    hwnds = []
    
    def enum_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            if window_pid == pid:
                results.append(hwnd)
        return True
    
    win32gui.EnumWindows(enum_callback, hwnds)
    
    if hwnds:
        return hwnds[0]  # 返回第一个找到的窗口
    return 0

def send_char_to_window(hwnd: int, char: str):
    """
    使用 Windows API 向窗口发送字符
    支持中文Unicode字符
    """
    if not hwnd:
        return
    
    # 方法1: 使用 WM_CHAR 消息（推荐）
    for c in char:
        # 发送 WM_CHAR 消息
        user32.SendMessageW(hwnd, WM_CHAR, ord(c), 0)
        time.sleep(0.005)  # 小延迟，避免发送太快

def send_backspace(hwnd: int, count: int = 1):
    """发送退格键"""
    if not hwnd:
        return
    
    for _ in range(count):
        user32.SendMessageW(hwnd, WM_KEYDOWN, VK_BACK, 0)
        user32.SendMessageW(hwnd, WM_KEYUP, VK_BACK, 0)
        time.sleep(0.01)

# ─────────────────────────────────────────────────────────────
# GuiBot 类 (v2 - 使用 Windows API)
# ─────────────────────────────────────────────────────────────

class GuiBot:
    """
    一个 GuiBot 对应：
      - 1 个真实的客户端 GUI 窗口
      - 1 个 WebSocket 连接（用于获取 match_begin 中的比赛文本）
      - 使用 Windows API 发送键盘输入（不依赖 pywinauto 控件识别）
    """

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 8888):
        self.name = name
        self.host = host
        self.port = port
        self.process = None           # subprocess.Popen
        self.hwnd = 0                # 窗口句柄
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

    # ── 查找窗口句柄 ────────────────────────────────────
    def find_window(self, timeout: int = 30) -> bool:
        """
        通过进程 ID 查找窗口句柄
        添加重试逻辑，因为窗口可能不会立即出现
        """
        if not WIN32GUI_AVAILABLE:
            log(f"⚠️  pywin32 未安装，无法查找窗口", self.name)
            return False

        if not self.process or not self.process.pid:
            log(f"❌ 进程未启动", self.name)
            return False

        log(f"正在查找窗口 (PID={self.process.pid})...", self.name)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            hwnd = find_window_by_pid(self.process.pid)
            if hwnd:
                self.hwnd = hwnd
                try:
                    title = win32gui.GetWindowText(hwnd)
                    log(f"✅ 找到窗口: HWND={hwnd}, 标题='{title}'", self.name)
                    return True
                except Exception:
                    log(f"✅ 找到窗口: HWND={hwnd}", self.name)
                    return True
            
            log(f"⏳ 窗口尚未创建，{timeout - int(time.time() - start_time)} 秒后重试...", self.name)
            time.sleep(2)

        log(f"❌ 查找窗口失败 (超时 {timeout} 秒)", self.name)
        return False

    # ── 聚焦窗口 ────────────────────────────────────────
    def focus_window(self) -> bool:
        """将窗口带到前台并聚焦"""
        if not self.hwnd:
            log(f"❌ 没有窗口句柄", self.name)
            return False

        try:
            # 方法1: 使用 win32gui
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.2)
            return True
        except Exception as e:
            log(f"⚠️  聚焦窗口失败: {e}", self.name)
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
                            if self.hwnd:
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
        """在 GUI 窗口中模拟人类打字（使用 Windows API）"""
        if not self.match_text:
            log(f"❌ 没有比赛文本，无法打字", self.name)
            return

        if not self.hwnd:
            log(f"❌ 没有窗口句柄", self.name)
            return

        # 等待倒计时结束 + 人类延迟
        delay = random.uniform(*START_DELAY)
        log(f"⏳ 等待 {delay:.1f} 秒后开始打字...", self.name)
        time.sleep(delay)

        # 聚焦窗口（确保输入框可以接收键盘输入）
        log(f"🎯 正在聚焦窗口...", self.name)
        self.focus_window()
        time.sleep(0.3)

        # 注意：客户端在比赛开始时会自动聚焦输入框
        # 所以我们不需要手动点击输入框

        # 人类模拟打字参数
        target_pct = random.uniform(COMPLETION_MIN, COMPLETION_MAX)
        target_len = int(len(self.match_text) * target_pct)
        errors = 0

        log(f"📝 目标: {target_len}/{len(self.match_text)} 字 ({target_pct*100:.0f}%)", self.name)
        log(f"🎯 开始打字...", self.name)

        # 逐字打字
        for i in range(target_len):
            if not self.match_active:
                log(f"⏹️  比赛已结束，停止打字", self.name)
                break

            char = self.match_text[i]

            # 偶尔打错（输入一个错误字符，然后删除）
            if random.random() < ERROR_RATE:
                wrong_char = chr(ord(char) + random.choice([-2, -1, 1, 2]))
                try:
                    send_char_to_window(self.hwnd, wrong_char)
                    time.sleep(0.05)
                    send_backspace(self.hwnd, 1)
                    errors += 1
                except Exception:
                    pass

            # 输入正确字符
            try:
                send_char_to_window(self.hwnd, char)
            except Exception as e:
                log(f"⚠️  发送字符失败: {e}", self.name)

            # 按键间延迟（模拟人类变速）
            delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)

            # 偶尔犹豫（模拟"思考"）
            if random.random() < HESITATE_CHANCE:
                delay += random.uniform(*HESITATE_TIME)

            time.sleep(delay)

        log(f"✅ 打字完成! (错误: {errors} 个)", self.name)

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
    print(" " * 15 + "打字对战 - GUI 自动化测试机器人 v2")
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
    if not WIN32GUI_AVAILABLE:
        log("⚠️  pywin32 未安装，正在尝试安装...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pywin32"],
                check=True,
            )
            log("✅ pywin32 安装成功，请重新运行脚本")
        except Exception as e:
            log(f"❌ 无法安装 pywin32: {e}")
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

    log(f"✅ 已启动 {len(bots)} 个 GUI 窗口，开始查找窗口...")

    # 4. 查找每个 bot 的窗口句柄
    print()
    log("🔍 正在查找窗口句柄...")
    connected_bots = []
    for i, bot in enumerate(bots):
        log(f"查找 {i+1}/{len(bots)}: {bot.name}...")
        if bot.find_window(timeout=30):
            connected_bots.append(bot)
        time.sleep(0.5)

    if len(connected_bots) == 0:
        log("⚠️  没有成功找到任何窗口，打字功能将不可用")
        log("   提示: 请检查客户端是否正常启动，或查看日志")
    else:
        log(f"✅ 已找到 {len(connected_bots)}/{len(bots)} 个窗口")

    # 5. 启动 WebSocket 监听（获取比赛文本）
    print()
    log("📡 正在启动 WebSocket 监听...")
    for bot in connected_bots:
        bot.start_ws_listener()
        time.sleep(0.5)

    # 6. 提示用户操作
    print()
    print("=" * 62)
    print("  🎯 操作步骤：")
    print()
    print("  1️⃣  确保服务端已启动（运行 server/main.py 或 YDZServer.exe）")
    print("  2️⃣  在服务端界面点击『▶ 开始比赛』")
    print("  3️⃣  等待倒计时结束，机器人将自动开始打字")
    print()
    print("  💡 提示: 机器人会模拟人类行为（变速、偶尔打错、不完全打完）")
    print("  💡 v2版本使用 Windows API 发送键盘消息，不依赖 pywinauto 控件识别")
    print()
    print("  按 Ctrl+C 退出并关闭所有窗口")
    print("=" * 62)
    print()

    # 7. 保持主线程运行，等待用户中断
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        log("收到中断信号，正在清理...")

    # 8. 清理所有机器人进程
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
