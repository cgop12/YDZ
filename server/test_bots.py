"""测试脚本 — 启动GUI客户端窗口 + 模拟真人打字"""

import asyncio
import json
import random
import time
import sys
import subprocess
import os
import websockets

# ═══ 配置 ═══
HOST = "127.0.0.1"
PORT = 8888
BOT_COUNT = 5
TYPING_SPEED = 0.07        # 每字间隔(模拟真人)
CLIENT_EXE = r"D:\type_battle\TypeBattleClient\TypeBattleClient.exe"

SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张"
GIVENS = "明伟芳敏静洋涛昊爽悦强毅峰雪琳辉建国志文"


def rname():
    return random.choice(SURNAMES) + random.choice(GIVENS) + random.choice(GIVENS)


def encode(d):
    return json.dumps(d, ensure_ascii=False)


async def bot_with_gui(name: str):
    """启动GUI客户端 + WebSocket模拟打字"""

    # ═══ 1. 启动GUI客户端 ═══
    proc = None
    if os.path.exists(CLIENT_EXE):
        proc = subprocess.Popen(
            [CLIENT_EXE, "--name", name, "--host", HOST, "--port", str(PORT)],
            cwd=os.path.dirname(CLIENT_EXE),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        print(f"[GUI] {name} 窗口已启动 (PID={proc.pid})")
    else:
        print(f"[GUI] 找不到客户端exe，仅WS模式 - {name}")

    await asyncio.sleep(1.5)  # 等客户端连接

    # ═══ 2. WS机器人（用不同名，避免与GUI客户端冲突） ═══
    bot_name = name + "⊙"
    uri = f"ws://{HOST}:{PORT}"
    async with websockets.connect(uri) as ws:
        await ws.send(encode({"type": "join", "name": bot_name}))
        resp = json.loads(await ws.recv())
        if resp.get("type") != "join_ack":
            print(f"[{bot_name}] 加入失败: {resp}")
            if proc: proc.terminate()
            return
        print(f"[{bot_name}] 机器人已就绪")

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=180)
            except asyncio.TimeoutError:
                break

            msg = json.loads(raw)
            t = msg.get("type", "")

            if t == "countdown":
                print(f"[{bot_name}] ⏳ {msg['seconds']}秒倒计时...")

            elif t == "match_begin":
                text = msg["text"]
                opp = msg["opponent_name"]
                dur = msg["time_limit"]
                print(f"[{bot_name}] 🏁 vs {opp} | {len(text)}字/{dur}秒")

                # ═══ 模拟真人打字 ═══
                start = time.time()
                # 真人特点: 不会打完, 有快有慢
                target_pct = random.uniform(0.55, 0.95)  # 完成55%~95%
                target = int(len(text) * target_pct)
                errors = random.randint(0, max(1, target // 15))

                last_progress_time = start
                for i in range(target):
                    ch = text[i] if i < len(text) else "?"

                    # 偶尔打错(4%概率)
                    if random.random() < 0.04 and ord(ch) > 128:
                        ch = chr(ord(ch) + random.choice([1, -1]))

                    await ws.send(encode({
                        "type": "keystroke", "char": ch, "index": i}))

                    # 每200ms上报一次进度(真人不会每秒报)
                    now = time.time()
                    if now - last_progress_time >= 0.2:
                        e = now - start
                        await ws.send(encode({
                            "type": "progress", "completed": i + 1,
                            "errors": min(errors, i), "elapsed": e}))
                        last_progress_time = now

                    # 模拟真人变速: 时而快时而慢
                    base_delay = TYPING_SPEED
                    if random.random() < 0.1:  # 10%概率犹豫
                        base_delay += random.uniform(0.05, 0.15)
                    await asyncio.sleep(base_delay + random.uniform(-0.02, 0.02))

                elapsed = time.time() - start
                await ws.send(encode({
                    "type": "progress", "completed": target,
                    "errors": errors, "elapsed": elapsed}))
                print(f"[{bot_name}] ✅ {target}/{len(text)}字 | {errors}错 | {elapsed:.1f}s | {target_pct*100:.0f}%")

            elif t == "round_end":
                s = msg["my_result"]["score"]
                print(f"[{bot_name}] 🏅 本轮得分: {s}")

            elif t == "final_ranking" or t == "tournament_over":
                for r in msg.get("ranking", []):
                    if r["name"] == bot_name:
                        print(f"[{bot_name}] 🏆 最终排名: 第{r['rank']}名")
                        break
                break

            elif t == "force_end":
                print(f"[{name}] ⛔ 比赛终止")
                break

            elif t == "paused":
                print(f"[{name}] ⏸ 暂停/恢复")

            elif t == "opponent_left":
                print(f"[{name}] 👋 对手退出")

            elif t == "error":
                print(f"[{name}] ❌ {msg.get('message')}")

    # 清理
    if proc:
        proc.terminate()
        try:
            proc.wait(2)
        except Exception:
            proc.kill()


async def main():
    print(f"╔══════════════════════════════╗")
    print(f"║   打字对战 · 自动化测试      ║")
    print(f"║   启动 {BOT_COUNT} 个客户端窗口     ║")
    print(f"║   连接 {HOST}:{PORT}             ║")
    print(f"╚══════════════════════════════╝")
    print()

    names = [rname() for _ in range(BOT_COUNT)]
    print("选手名单:", ", ".join(names))
    print()

    await asyncio.gather(*(bot_with_gui(n) for n in names))

    print("\n" + "=" * 40)
    print("  全部完成! 窗口已自动关闭")
    print("=" * 40)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BOT_COUNT = int(sys.argv[1])
    asyncio.run(main())
