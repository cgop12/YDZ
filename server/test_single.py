"""
单窗口测试版
先试一个客户端，确保能正常打字
"""

import subprocess
import time
import random
import os

CLIENT_PATHS = [
    r"D:\ydz\client\dist\YDZClient.exe",
    r"D:\ydz\client\YDZClient.exe",
    r"D:\ydz\YDZClient.exe",
]

def find_client():
    for p in CLIENT_PATHS:
        if os.path.exists(p):
            return p
    return None

def log(msg):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def main():
    print()
    print("╔══════════════════════════════════╗")
    print("║   单窗口 UI 测试版                ║")
    print("╚══════════════════════════════════╝")
    print()

    # 1. 找 EXE
    log("查找客户端...")
    client_exe = find_client()
    if not client_exe:
        log("❌ 找不到客户端 EXE！")
        return
    log(f"✅ 找到: {client_exe}")

    # 2. 检查 pywinauto
    try:
        import pywinauto
        from pywinauto import Application
        log("✅ pywinauto 可用")
    except ImportError:
        log("❌ 请先安装: pip install pywinauto")
        return

    # 3. 启动
    log("启动客户端...")
    proc = subprocess.Popen(
        [
            client_exe,
            "--name", "测试选手",
            "--host", "127.0.0.1",
            "--port", "8888"
        ],
        cwd=os.path.dirname(client_exe),
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    log(f"✅ 已启动 (PID={proc.pid})")

    # 4. 等窗口
    log("⏳ 等待 5 秒，让客户端连接...")
    time.sleep(5)

    # 5. 连接窗口
    try:
        log("连接窗口...")
        app = Application(backend="uia").connect(title="打字对战", timeout=15)
        window = app.window(title="打字对战")
        log("✅ 窗口已连接")
    except Exception as e:
        log(f"❌ 连接窗口失败: {e}")
        return

    # 6. 找输入框
    try:
        log("查找输入框...")
        input_box = window.child_window(control_type="Edit", found_index=0)
        log("✅ 找到输入框")
    except Exception as e:
        log(f"❌ 找不到输入框: {e}")
        return

    # 7. 提示
    print()
    print("=" * 50)
    print("  请先在服务端开始比赛！")
    print("  等倒计时结束，比赛开始，输入框启用后，")
    print("  再按 Enter 开始打字测试！")
    print("=" * 50)
    print()
    input("按 Enter 继续...")

    # 8. 打字测试
    print()
    log("开始打字测试...")

    # 激活
    try:
        window.set_focus()
        time.sleep(0.3)
        input_box.set_focus()
        input_box.click()
        time.sleep(0.3)
        input_box.set_text("")
        log("✅ 输入框已激活")
    except Exception as e:
        log(f"⚠️  激活问题: {e}")

    # 打字
    test_text = "春眠不觉晓处处闻啼鸟夜来风雨声花落知多少"
    log(f"打这段: {test_text}")

    for char in test_text:
        try:
            input_box.type_keys(char, with_spaces=True, pause=0.01)
        except:
            pass
        time.sleep(random.uniform(0.05, 0.12))

    log("✅ 打字完成！")

    print()
    input("按 Enter 关闭窗口...")

    # 9. 清理
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except:
        proc.kill()
    log("✅ 已关闭")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断")
