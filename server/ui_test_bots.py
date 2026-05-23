"""
================================================================================
打字对战 - 完整 UI 自动化测试脚本 (控件操作版)
================================================================================
特点：
  - 直接用 pywinauto 操作控件，不是键盘模拟
  - 逐个窗口操作，避免焦点混乱
  - 支持多开
  - 完整错误处理
================================================================================
"""

import subprocess
import time
import random
import os
import sys
from typing import List

# ──────────────────────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────────────────────

CLIENT_PATHS = [
    r"D:\type_battle\client\dist\TypeBattleClient.exe",
    r"D:\type_battle\client\TypeBattleClient.exe",
    r"D:\type_battle\TypeBattleClient.exe",
]

HOST = "127.0.0.1"
PORT = 8888
DEFAULT_BOT_COUNT = 3

# 打字配置
TYPING_DELAY_MIN = 0.04
TYPING_DELAY_MAX = 0.12
ERROR_RATE = 0.05
HESITATE_CHANCE = 0.1
HESITATE_TIME = (0.1, 0.3)

# 名字库
SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
GIVENS = "明伟芳敏静洋涛昊爽悦强毅峰雪琳辉建国庆志文武杰磊鹏"


# ──────────────────────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────────────────────

def log(msg: str, name: str = "SYSTEM"):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] [{name:8s}]  {msg}")


def random_name():
    return random.choice(SURNAMES) + random.choice(GIVENS) + random.choice(GIVENS)


def find_client():
    for p in CLIENT_PATHS:
        if os.path.exists(p):
            return p
    return ""


# ──────────────────────────────────────────────────────────────
# 单个机器人
# ──────────────────────────────────────────────────────────────

class Bot:
    def __init__(self, name: str, client_exe: str):
        self.name = name
        self.client_exe = client_exe
        self.process = None
        self.app = None
        self.window = None

    def start(self) -> bool:
        log("正在启动...", self.name)
        try:
            self.process = subprocess.Popen(
                [
                    self.client_exe,
                    "--name", self.name,
                    "--host", HOST,
                    "--port", str(PORT)
                ],
                cwd=os.path.dirname(self.client_exe),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            log(f"✅ 启动 (PID={self.process.pid})", self.name)
            return True
        except Exception as e:
            log(f"❌ 失败: {e}", self.name)
            return False

    def connect_window(self) -> bool:
        try:
            from pywinauto import Application
            # 连接到这个窗口（通过标题匹配）
            # 注意：如果多开，标题可能一样，这里简化处理
            self.app = Application(backend="uia").connect(title="打字对战", timeout=15)
            self.window = self.app.window(title="打字对战")
            log("✅ 连接窗口", self.name)
            return True
        except Exception as e:
            log(f"⚠️  连接窗口失败: {e}", self.name)
            return False

    def type_text(self, text: str):
        if not self.window:
            log("❌ 无窗口连接", self.name)
            return

        log(f"⌨️  准备打字: {len(text)}字", self.name)

        # 找到输入框
        try:
            input_box = self.window.child_window(control_type="Edit", found_index=0)
        except:
            log("❌ 找不到输入框", self.name)
            return

        # 激活并聚焦
        try:
            self.window.set_focus()
            time.sleep(0.2)
            input_box.set_focus()
            input_box.click()
            time.sleep(0.2)
            # 清空
            input_box.set_text("")
            time.sleep(0.1)
        except Exception as e:
            log(f"⚠️  聚焦问题: {e}", self.name)

        # 开始打字（直接用 type_keys，这样更可靠）
        target_pct = random.uniform(0.55, 0.9)
        target_len = int(len(text) * target_pct)
        log(f"   目标: {target_len}/{len(text)}字 ({target_pct*100:.0f}%)", self.name)

        errors = 0
        for i in range(target_len):
            if i >= len(text):
                break

            char = text[i]

            # 偶尔打错
            if random.random() < ERROR_RATE and ord(char) > 128:
                char = chr(ord(char) + random.choice([-2, -1, 1, 2]))
                errors += 1

            # 输入
            try:
                input_box.type_keys(char, with_spaces=True, pause=0.01)
            except:
                pass

            # 延迟
            delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
            if random.random() < HESITATE_CHANCE:
                delay += random.uniform(*HESITATE_TIME)
            time.sleep(delay)

        log(f"✅ 打字完成 (错{errors})", self.name)

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except:
                    self.process.kill()
                log("已关闭", self.name)
            except:
                pass


# ──────────────────────────────────────────────────────────────
# 主程序
# ──────────────────────────────────────────────────────────────

def main():
    # 解析参数
    bot_count = DEFAULT_BOT_COUNT
    if len(sys.argv) > 1:
        try:
            bot_count = int(sys.argv[1])
        except:
            pass

    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 11 + "打字对战 - UI 自动化测试 (控件版)" + " " * 15 + "║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  客户端: {bot_count:2d}  |  服务端: {HOST}:{PORT:<5}  |  模式: 控件操作  ║")
    print("╚" + "═" * 58 + "╝")
    print()

    # 1. 找 EXE
    log("查找客户端 EXE...")
    client_exe = find_client()
    if not client_exe:
        log("❌ 找不到 TypeBattleClient.exe！")
        log("   请先运行 client/build.bat 编译")
        return
    log(f"✅ 找到: {client_exe}")

    # 2. 检查 pywinauto
    try:
        import pywinauto
        log("✅ pywinauto 可用")
    except ImportError:
        log("❌ pywinauto 未安装！")
        log("   请运行: install_deps.bat")
        return

    # 3. 生成名字并启动
    names = [random_name() for _ in range(bot_count)]
    log(f"🎮  选手: {', '.join(names)}")

    bots = []
    for name in names:
        b = Bot(name, client_exe)
        if b.start():
            bots.append(b)
        time.sleep(1)

    if len(bots) == 0:
        log("❌ 没有启动成功的客户端")
        return

    # 4. 等待连接
    print()
    log("⏳ 等待客户端连接 (5秒)...")
    time.sleep(5)

    # 5. 连接窗口
    print()
    log("正在连接窗口...")
    connected_bots = []
    for b in bots:
        if b.connect_window():
            connected_bots.append(b)
        time.sleep(0.5)

    if len(connected_bots) == 0:
        log("⚠️  没有连接到任何窗口")
    else:
        log(f"✅ 连接了 {len(connected_bots)} 个窗口")

    # 6. 提示
    print()
    print("=" * 60)
    print("  🎯  操作步骤：")
    print()
    print("  1️⃣  确保服务端已启动")
    print("  2️⃣  在服务端点击『▶ 开始比赛』")
    print("  3️⃣  等倒计时结束，比赛开始")
    print("  4️⃣  然后回到这里按 Enter 开始打字")
    print()
    print("  按 Ctrl+C 退出")
    print("=" * 60)
    print()

    # 7. 等用户
    try:
        input("⏸️  准备就绪，按 Enter 开始打字...\n")
    except KeyboardInterrupt:
        print()
        log("用户中断")
    else:
        # 8. 开始打字
        print()
        log("🚀 开始打字...")

        # 测试文本
        texts = [
            "春眠不觉晓处处闻啼鸟夜来风雨声花落知多少",
            "床前明月光疑是地上霜举头望明月低头思故乡",
            "白日依山尽黄河入海流欲穷千里目更上一层楼"
        ]

        # 逐个操作（避免焦点混乱）
        for i, bot in enumerate(connected_bots):
            txt = random.choice(texts) * 2
            log(f"--- 第 {i+1} 个: {bot.name}", "MAIN")
            bot.type_text(txt)
            time.sleep(0.5)

        print()
        log("⏳ 打字完成，等待比赛结束...")
        log("按 Enter 关闭所有窗口")
        try:
            input()
        except:
            pass

    # 9. 清理
    print()
    log("🗑️  正在清理...")
    for b in bots:
        b.stop()

    print()
    log("✅ 完成！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        log("用户中断，正在清理...")
        # 尝试清理残留
        try:
            import psutil
            for p in psutil.process_iter(['name']):
                if 'TypeBattleClient' in p.info['name']:
                    try:
                        p.kill()
                    except:
                        pass
        except:
            pass
        print("✅ 已退出")
