"""打字对战服务端 — 统一协议层 + 统一模型层 + psutil 优先级"""

import sys, os, asyncio, json, time, uuid, random, socket, re, traceback
from datetime import datetime

if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_BASE))

try:
    import psutil
    _psutil_available = True
except ImportError:
    _psutil_available = False

from common.logger import setup_logger, get_logger
from common.protocol import (
    encode, decode,
    C_JOIN, C_PROGRESS, C_PONG,
    C_ADMIN_START, C_PAUSE_REQUEST, C_RESUME_REQUEST,
    C_ADMIN_END, C_RECONNECT, C_READY,
    s_join_ack, s_player_list, s_countdown, s_match_begin,
    s_round_end, s_final_ranking,
    s_pause_broadcast, s_resume_broadcast, s_time_sync,
    s_ready_status, s_full_state, s_force_end, s_error, s_ping,
)
from common.models import Player, Match, Tournament
from common.pinyin_texts import get_pinyin_text


# 标点统一 — 发送给客户端前将所有英文标点转为中文
PUNCT_TO_CN = {
    ',': '，', '.': '。', '?': '？', '!': '！',
    ';': '；', ':': '：', '(': '（', ')': '）',
    '[': '【', ']': '】',
}

def _normalize_text(text: str) -> str:
    return ''.join(PUNCT_TO_CN.get(c, c) for c in text)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

UDP_PORT = 23333


def get_safe_icon(icon_filename: str) -> QIcon:
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(base_path, icon_filename)

    if os.path.exists(icon_path):
        return QIcon(icon_path)
    else:
        return QIcon()

DISCOVER_MAGIC = b"type_battle_discover"
BROADCAST_PREFIX = "TYPING_SERVER:"
DEFAULT_TIME_LIMIT = 60
TEXT_LENGTH_MIN = 50
TEXT_LENGTH_MAX = 80

def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def global_exception_handler(exc_type, exc_value, exc_tb):
    base_dir = get_app_base_dir()
    logs_dir = os.path.join(base_dir, "logs")
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except Exception:
        pass
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_file = os.path.join(logs_dir, f"crash_server_{ts}.log")
    try:
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write(f"=== 打字对战服务端崩溃日志 ===\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 60 + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    try:
        logger = get_logger("server")
        logger.critical("服务端崩溃", exc_info=(exc_type, exc_value, exc_tb))
    except Exception:
        pass
    try:
        from PyQt6.QtWidgets import QMessageBox
        QTimer.singleShot(0, lambda: QMessageBox.critical(
            None, "服务端异常",
            f"服务端发生异常，已记录崩溃日志:\n{crash_file}"))
    except Exception:
        pass
    if sys.__excepthook__ is not None:
        sys.__excepthook__(exc_type, exc_value, exc_tb)

BUILTIN_TEXTS = [
    "春眠不觉晓,处处闻啼鸟。夜来风雨声,花落知多少。",
    "床前明月光,疑是地上霜。举头望明月,低头思故乡。",
    "白日依山尽,黄河入海流。欲穷千里目,更上一层楼。",
    "锄禾日当午,汗滴禾下土。谁知盘中餐,粒粒皆辛苦。",
    "离离原上草,一岁一枯荣。野火烧不尽,春风吹又生。",
    "远上寒山石径斜,白云生处有人家。停车坐爱枫林晚,霜叶红于二月花。",
    "两个黄鹂鸣翠柳,一行白鹭上青天。窗含西岭千秋雪,门泊东吴万里船。",
    "朝辞白帝彩云间,千里江陵一日还。两岸猿声啼不住,轻舟已过万重山。",
    "故人西辞黄鹤楼,烟花三月下扬州。孤帆远影碧空尽,唯见长江天际流。",
    "千山鸟飞绝,万径人踪灭。孤舟蓑笠翁,独钓寒江雪。",
]

DATA_DIR = os.path.join(get_app_base_dir(), "data")
TEXT_FILE = os.path.join(DATA_DIR, "texts.json")

class TextManager:
    def __init__(self):
        self.texts = []
        self.current_text_name = ""
        os.makedirs(DATA_DIR, exist_ok=True)
        self._load()

    def _load(self):
        if os.path.exists(TEXT_FILE):
            try:
                with open(TEXT_FILE, "r", encoding="utf-8") as f:
                    self.texts = json.load(f).get("texts", [])
            except Exception:
                self.texts = []
        if not self.texts:
            self.texts = BUILTIN_TEXTS.copy()

    def _save(self):
        with open(TEXT_FILE, "w", encoding="utf-8") as f:
            json.dump({"texts": self.texts}, f, ensure_ascii=False, indent=2)

    def import_txt(self, filepath):
        if not os.path.exists(filepath):
            return 0
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        added = 0
        for line in lines:
            clean = re.sub(r'[，,。.!！?？、;；:：""''（）()\\s]', '', line)
            if TEXT_LENGTH_MIN <= len(clean) <= TEXT_LENGTH_MAX and line not in self.texts:
                self.texts.append(line)
                added += 1
        if added:
            self._save()
        return added

    def add_text(self, text):
        text = text.strip()
        if not text:
            return False
        clean = re.sub(r'[，,。.!！?？、;；:：""''（）()\\s]', '', text)
        if TEXT_LENGTH_MIN <= len(clean) <= TEXT_LENGTH_MAX and text not in self.texts:
            self.texts.append(text)
            self._save()
            return True
        return False

    def remove_text(self, idx):
        if 0 <= idx < len(self.texts):
            self.texts.pop(idx)
            self._save()
            return True
        return False

    def get_all(self):
        return self.texts

    def count(self):
        return len(self.texts)

    def pick_random(self, exclude=None):
        pool = [t for t in self.texts if not exclude or t not in exclude] or self.texts
        return random.choice(pool)

    def pick_batch(self, n, exclude=None):
        pool = [t for t in self.texts if not exclude or t not in exclude]
        random.shuffle(pool)
        return pool[:n]


class GameServer(QThread):
    log = pyqtSignal(str)
    player_status = pyqtSignal(str, str)  # (pid, status_text)
    players_changed = pyqtSignal(int, list)
    matches_update = pyqtSignal(int, list)
    ranking_ready = pyqtSignal(list)
    status = pyqtSignal(str)
    progress = pyqtSignal(str, str, str, str)
    player_offline_signal = pyqtSignal(str, str)
    round_started = pyqtSignal(str)
    round_finished = pyqtSignal(str)
    kick_request = pyqtSignal(str)

    def __init__(self, host="0.0.0.0", port=8888):
        super().__init__()
        self.host = host
        self.port = port
        self.tm = TextManager()
        self.tournament = Tournament(self.tm)
        self.time_limit = DEFAULT_TIME_LIMIT
        self._paused = False
        self._match_remaining = DEFAULT_TIME_LIMIT
        self.running = False
        self._loop = None
        self._ws = {}
        self._ready = {}
        self._disconnected = {}
        self._last_heartbeat = {}
        self._udp_transport = None
        self._udp_protocol = None
        self.logger = get_logger("server")
        self._lock = None
        self._force_ended = False
        self._early_finished: set[str] = set()  # 提前结束的对局 {

    def _get_lan_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return socket.gethostbyname(socket.gethostname())

    def run(self):
        if _psutil_available:
            try:
                p = psutil.Process()
                p.set_cpu_priority(psutil.HIGH_PRIORITY_CLASS if sys.platform == "win32" else 10)
            except Exception:
                pass
        try:
            self.running = True
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.critical("GameServer 线程崩溃", exc_info=True)
            raise
        finally:
            # 确保 UDP transport 关闭释放端口
            if self._udp_transport and not self._udp_transport.is_closing():
                try:
                    self._udp_transport.close()
                except Exception:
                    pass
            # 关闭 event loop
            if self._loop and not self._loop.is_closed():
                try:
                    # 执行残留的回调（如 transport.close() 的清理）
                    self._loop.run_until_complete(asyncio.sleep(0.1))
                except Exception:
                    pass
                try:
                    self._loop.close()
                except Exception:
                    pass

    async def _serve(self):
        import websockets
        from websockets.server import serve
        self._lock = asyncio.Lock()
        asyncio.create_task(self._udp())
        asyncio.create_task(self._heartbeat_loop())
        async def h(ws):
            await self._handle(ws)
        self.log.emit(f"WebSocket ws://{self._get_lan_ip()}:{self.port}")
        self.logger.info(f"WebSocket服务启动在 ws://{self._get_lan_ip()}:{self.port}")
        self.status.emit("等待玩家...")
        try:
            async with serve(h, self.host, self.port, reuse_address=True):
                await asyncio.Future()
        except asyncio.CancelledError:
            # 优雅关闭：先关 UDP transport，释放端口
            if self._udp_transport and not self._udp_transport.is_closing():
                self._udp_transport.close()
            pass
        except Exception as e:
            self.logger.exception(f"WebSocket服务异常: {e}")
            raise

    async def _udp(self):
        loop = asyncio.get_event_loop()
        class U:
            def __init__(s, p):
                s.p = p
            def connection_made(s, t):
                s.t = t
                sock = t.get_extra_info('socket')
                if sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            def datagram_received(s, d, a):
                try:
                    if d == DISCOVER_MAGIC:
                        r = f"{BROADCAST_PREFIX}{s.p._get_lan_ip()}:{s.p.port}".encode()
                        try:
                            s.t.sendto(r, a)
                        except Exception:
                            pass
                except Exception:
                    pass
        try:
            self.logger.info("启动UDP服务发现")
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: U(self),
                local_addr=("0.0.0.0", UDP_PORT),
                allow_broadcast=True)
            self._udp_transport = transport
            self._udp_protocol = protocol
        except socket.error as e:
            self.log.emit(f"UDP错误: {e}")
            self.logger.error(f"UDP socket创建失败: {e}")
        except Exception as e:
            self.log.emit(f"UDP失败: {e}")

    async def _handle(self, ws):
        pid = ""
        try:
            async for raw in ws:
                try:
                    msg = decode(raw)
                    if msg is None:
                        continue
                    npid = await self._dispatch(ws, msg, pid)
                    if not pid and npid:
                        pid = npid
                except Exception as e:
                    self.logger.warning(f"处理WebSocket消息时异常: {e}")
        except Exception as e:
            self.logger.exception(f"WebSocket处理异常: {e}")
        finally:
            if pid:
                self._ws.pop(pid, None)
                self.tournament.remove_player(pid)
                await self._broadcast_players()

    async def _dispatch(self, ws, msg, pid):
        t = msg.get("t", "")

        if t == C_JOIN:
            name = msg.get("n", "").strip()
            if not name:
                await ws.send(s_error("INVALID_MESSAGE", "名字不能为空"))
                return ""
            if len(name) > 16:
                await ws.send(s_error("INVALID_MESSAGE", "名字长度需在1-16字符之间"))
                return ""
            async with self._lock:
                pid, err = self.tournament.add_player(name)
                if err:
                    await ws.send(s_error("NAME_TAKEN", err))
                    return ""
                self._ws[pid] = ws
                self._last_heartbeat[pid] = time.time()
            await ws.send(s_join_ack(pid, name, self.tournament.player_list(),
                                     len(self.tournament.players), f"#{self.port}"))
            await self._broadcast_players()
            self.log.emit(f"加入: {name}")
            self.status.emit(f"{len(self.tournament.players)}/32")
            return pid

        if not pid:
            await ws.send(s_error("INVALID_MESSAGE", "请先加入"))
            return ""

        elif t == C_PROGRESS:
            if self._paused:
                return ""
            m = self.tournament.get_match_for(pid)
            if m:
                comp = msg.get("c", 0)
                errs = msg.get("e", 0)
                ela = msg.get("l", 0)
                m.update(pid, comp, errs, ela)
                name = m.p1.name if pid == m.p1.id else m.p2.name
                spd = f"{comp / max(ela, 0.1):.1f}"
                acc = f"{(comp - errs) / max(comp, 1) * 100:.0f}%" if comp else "--"
                self.progress.emit(name, spd, acc, "比赛中")

                # 选手完成全部字符 → 立即结束该场对决
                if not m.finished and comp >= len(m.text):
                    m.decide_winner()
                    self._early_finished.add(id(m))
                    await ws.send(s_round_end(
                        m.winner.name if m.winner else "?",
                        m.get_result(m.p1.id).to_dict(),
                        m.get_result(m.p2.id).to_dict()))
                    opp_ws = self._ws.get(m.p1.id if pid == m.p2.id else m.p2.id)
                    if opp_ws:
                        await opp_ws.send(s_round_end(
                            m.winner.name if m.winner else "?",
                            m.get_result(m.p2.id if pid == m.p1.id else m.p1.id).to_dict(),
                            m.get_result(m.p1.id if pid == m.p2.id else m.p2.id).to_dict()))

        elif t == C_PONG:
            self._last_heartbeat[pid] = time.time()

        elif t == C_READY:
            self._ready[pid] = msg.get("r", True)
            all_ok = all(self._ready.get(p, False) for p in self._ws)
            await self._broadcast(s_ready_status(self._ready, all_ok))

        elif t == C_RECONNECT:
            rpid = msg.get("p", "")
            if rpid in self._disconnected:
                p, _ = self._disconnected.pop(rpid)
                self._ws[rpid] = ws
                self._last_heartbeat[rpid] = time.time()
                m = self.tournament.get_match_for(rpid)
                if m:
                    opp = m.p2 if rpid == m.p1.id else m.p1
                    my_r = m.get_result(rpid)
                    opp_r = m.get_result(opp.id)
                    await ws.send(s_full_state(
                        rpid,
                        int(self._match_remaining * 1000),
                        self._paused,
                        self.tournament.current_round,
                        self.tournament.round_name(),
                        opp.name,
                        m.text, len(m.text), self.time_limit,
                        {"completed": my_r.completed, "errors": my_r.errors},
                        {"completed": opp_r.completed, "errors": opp_r.errors},
                        self.tournament.player_list(),
                        pinyin_text=m.pinyin_text))
                    self.log.emit(f"{p.name} 已重连")
                else:
                    # 比赛已结束或未开始,重连后直接回大厅
                    await ws.send(s_join_ack(
                        rpid, p.name, self.tournament.player_list(),
                        len(self.tournament.players), f"#{self.port}"))
                    self.log.emit(f"{p.name} 已重连(等待中)")
                return rpid
            else:
                await ws.send(s_error("RECONNECT_FAILED", "重连失败"))

        elif t == C_ADMIN_START:
            if pid != self.tournament.admin_id:
                await ws.send(s_error("NOT_ADMIN", "只有管理员可开始"))
                return ""
            if not self.tournament.can_start():
                await ws.send(s_error("SERVER_ERROR", "至少2人"))
                return ""
            self.log.emit("开始比赛")
            await self._run_tournament()

        elif t == C_PAUSE_REQUEST:
            if pid != self.tournament.admin_id:
                await ws.send(s_error("NOT_ADMIN", ""))
                return ""
            if self._paused:
                await ws.send(s_error("ALREADY_PAUSED", ""))
                return ""
            self._paused = True
            self.log.emit("暂停")
            await self._broadcast(s_pause_broadcast(int(self._match_remaining * 1000)))

        elif t == C_RESUME_REQUEST:
            if pid != self.tournament.admin_id:
                await ws.send(s_error("NOT_ADMIN", ""))
                return ""
            if not self._paused:
                return ""
            self._paused = False
            self.log.emit("恢复")
            await self._broadcast(s_resume_broadcast(int(self._match_remaining * 1000)))

        elif t == C_ADMIN_END:
            if pid != self.tournament.admin_id:
                await ws.send(s_error("NOT_ADMIN", ""))
                return ""
            self.log.emit("强制结束")
            self._force_ended = True
            self._match_remaining = 0
            await self._broadcast(s_force_end("管理员结束"))

        return ""

    async def _broadcast(self, msg):
        for p, ws in list(self._ws.items()):
            try:
                await ws.send(msg)
            except Exception:
                pass

    async def kick_player(self, pid: str, reason: str = "管理员踢出"):
        async with self._lock:
            if pid not in self._ws:
                return False
            p = self.tournament.players.get(pid)
            if p:
                self.log.emit(f"[时间] 选手 {p.name} 已退出比赛")
            try:
                ws = self._ws.pop(pid)
            except KeyError:
                return False
        try:
            await ws.send(s_force_end(reason))
            await ws.close()
        except Exception:
            pass
        self.tournament.remove_player(pid)
        await self._broadcast_players()
        return True

    async def _broadcast_players(self):
        pl = self.tournament.player_list()
        await self._broadcast(s_player_list(pl, len(pl)))
        self.players_changed.emit(len(pl), pl)

    async def _heartbeat_loop(self):
        while self.running:
            await asyncio.sleep(2)
            now = time.time()
            disconnected_players = []
            timeout_cleared = []
            ping_targets = []

            async with self._lock:
                for pid, ws in list(self._ws.items()):
                    if pid in self._last_heartbeat and now - self._last_heartbeat[pid] > 5:
                        p = self.tournament.players.get(pid)
                        if p:
                            self._disconnected[pid] = (p, now)
                            disconnected_players.append(p)
                            self.log.emit(f"{p.name} 掉线 (保留10秒可重连)")
                        self._ws.pop(pid, None)
                    else:
                        ping_targets.append(ws)

                for pid in list(self._disconnected):
                    p, t = self._disconnected[pid]
                    if now - t > 10:
                        self._disconnected.pop(pid, None)
                        self.tournament.remove_player(pid)
                        timeout_cleared.append(p)
                        self.log.emit(f"{p.name} 重连超时，已移除")

            for ws in ping_targets:
                try:
                    await ws.send(s_ping())
                except Exception:
                    pass

            if disconnected_players or timeout_cleared:
                await self._broadcast_players()

    async def _time_sync_loop(self):
        while self.running and self._match_remaining > 0:
            await asyncio.sleep(0.2)
            if self._match_remaining <= 0:
                break
            await self._broadcast(s_time_sync(int(self._match_remaining * 1000), self._paused))

    async def _send(self, pid, msg):
        ws = self._ws.get(pid)
        if ws:
            try:
                await ws.send(msg)
            except Exception:
                pass

    async def _run_tournament(self, custom_text: str = "", use_pinyin: bool = False):
        self._force_ended = False
        self._manual_mode = False
        self.tournament.init_tournament()
        await self._run_one_round(custom_text, use_pinyin)

    async def _run_one_round(self, custom_text: str = "", use_pinyin: bool = False):
        """运行一轮比赛，结束后信号通知 GUI，由 GUI 决定下一轮"""
        # 若是新一轮比赛（非接续），确保数据已初始化
        if self.tournament.current_round == 0 and not self.tournament.alive:
            self.tournament.init_tournament()
        # 标点统一为中文，避免客户端渲染重叠
        custom_text = _normalize_text(custom_text)
        pinyin_pool: list[str] = []
        if use_pinyin:
            from common.pinyin_texts import get_pinyin_text
            needed = (len(self.tournament.alive) + 1) // 2
            for _ in range(needed):
                entry = get_pinyin_text()
                pinyin_pool.append(entry["pinyin"])
                if not custom_text:
                    custom_text = entry["chinese"]
            if custom_text and not pinyin_pool:
                entry = get_pinyin_text()
                pinyin_pool.append(entry["pinyin"])

        self.log.emit(f"[DEBUG] 广播倒计时: 存活{len(self.tournament.alive)}人")
        await self._broadcast(s_countdown(5))
        self.log.emit("[DEBUG] 倒计时广播完成")
        await asyncio.sleep(5)
        needed = (len(self.tournament.alive) + 1) // 2
        texts_arg = [custom_text] * needed if custom_text else None
        matches = self.tournament.create_round_matches(
            custom_texts=texts_arg, custom_pinyin=pinyin_pool)
        if not matches:
            self.logger.error("创建赛程失败，无法继续比赛")
            self.log.emit("赛程创建失败，比赛结束")
            self._finish_tournament()
            return
        self._current_matches = matches
        self.matches_update.emit(self.tournament.current_round, matches)
        rn = self.tournament.round_name()
        for m in matches:
            self.player_status.emit(m.p1.id, "比赛中")
            self.player_status.emit(m.p2.id, "比赛中")
        for m in matches:
            if not m.text:
                m.text = "打字对战"
            pt = m.pinyin_text
            await self._send(m.p1.id, s_match_begin(
                self.tournament.current_round, rn, m.p2.name,
                m.text, len(m.text), self.time_limit, pt))
            await self._send(m.p2.id, s_match_begin(
                self.tournament.current_round, rn, m.p1.name,
                m.text, len(m.text), self.time_limit, pt))
        if self.tournament.bye_player:
            bp = self.tournament.bye_player
            self.player_status.emit(bp.id, "已轮空")
            # 轮空：不传赢家名字，客户端靠 score=100,elapsed=0 识别
            await self._send(bp.id, s_round_end("", {
                "completed": 0, "total": 1, "completion_rate": 100,
                "errors": 0, "accuracy": 100, "elapsed": 0, "score": 100
            }, {
                "completed": 0, "total": 1, "completion_rate": 0,
                "errors": 0, "accuracy": 0, "elapsed": 0, "score": 0
            }))
            self.log.emit(f"{bp.name} 轮空晋级")
        self.status.emit(f"{rn} 比赛中...")
        self._match_remaining = self.time_limit
        ts_task = asyncio.create_task(self._time_sync_loop())
        await self._countdown_loop()
        ts_task.cancel()
        try:
            await ts_task
        except asyncio.CancelledError:
            pass
        if self._force_ended:
            self._current_matches = matches
            self._finish_tournament()
            return
        self.tournament.finish_round(matches)
        for m in matches:
            if id(m) in self._early_finished:
                continue
            await self._send(m.p1.id, s_round_end(
                m.winner.name if m.winner else "?",
                m.get_result(m.p1.id).to_dict(),
                m.get_result(m.p2.id).to_dict()))
            await self._send(m.p2.id, s_round_end(
                m.winner.name if m.winner else "?",
                m.get_result(m.p2.id).to_dict(),
                m.get_result(m.p1.id).to_dict()))
        # 更新 GUI 选手状态
        for m in matches:
            if m.winner:
                self.player_status.emit(m.winner.id, "已晋级")
            if m.loser:
                self.player_status.emit(m.loser.id, "已淘汰")
                self.log.emit(f"💀 {m.loser.name} 已淘汰")
        self._early_finished.clear()
        self.log.emit(f"{rn} 结束")
        self.round_finished.emit(rn)

    def _finish_tournament(self):
        """结算最终排名"""
        if self._force_ended:
            return
        ranking = self.tournament.finish()
        self.log.emit("比赛全部结束!")
        self.ranking_ready.emit(ranking)
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._broadcast(s_final_ranking(ranking)), self._loop)
        self.status.emit("比赛结束")
        self.tournament.reset()
        self._paused = False

    async def _countdown_loop(self):
        TICK = 0.1
        while self._match_remaining > 0:
            if self._force_ended:
                break
            # 所有比赛都已提前结束 → 立即结束此轮
            if (hasattr(self, '_current_matches') and self._current_matches
                    and len(self._early_finished) >= len(self._current_matches)):
                self.log.emit("[DEBUG] 所有比赛已提前结束，跳过等待")
                break
            await asyncio.sleep(TICK)
            if self._paused:
                continue
            self._match_remaining = max(0, self._match_remaining - TICK)

    async def _start_round(self, name: str, text: str, player_ids: list):
        players = [self.tournament.players[pid] for pid in player_ids if pid in self.tournament.players]
        if len(players) < 2:
            self.log.emit("赛程至少需要2名选手")
            return
        random.shuffle(players)
        self.matches_update.emit(0, [])
        self.round_started.emit(name)
        self._manual_mode = True
        self.status.emit(f"{name} 比赛中...")
        self._current_manual_round = name
        needed = (len(players) + 1) // 2
        texts = self.tm.pick_batch(needed) if self.tm else []
        matches = []
        for i in range(0, len(players) - 1, 2):
            t = texts[i // 2] if i // 2 < len(texts) else text
            try:
                m = Match(players[i], players[i + 1], t or "打字对战")
                matches.append(m)
            except (ValueError, IndexError) as e:
                self.logger.warning(f"创建 Match 失败: {e}")
                continue
        self._current_matches = matches
        bye_player = players[-1] if len(players) % 2 == 1 else None
        if bye_player:
            await self._send(bye_player.id, s_round_end("", {
                "completed": 0, "total": 1, "completion_rate": 100,
                "errors": 0, "accuracy": 100, "elapsed": 0, "score": 100
            }, {
                "completed": 0, "total": 1, "completion_rate": 0,
                "errors": 0, "accuracy": 0, "elapsed": 0, "score": 0
            }))
            self.log.emit(f"{bye_player.name} 轮空晋级")
        for m in matches:
            pt = m.pinyin_text
            await self._send(m.p1.id, s_match_begin(0, name, m.p2.name, m.text, len(m.text), self.time_limit, pt))
            await self._send(m.p2.id, s_match_begin(0, name, m.p1.name, m.text, len(m.text), self.time_limit, pt))
        self._match_remaining = self.time_limit
        ts_task = asyncio.create_task(self._time_sync_loop())
        await self._countdown_loop()
        ts_task.cancel()
        try:
            await ts_task
        except asyncio.CancelledError:
            pass
        for m in matches:
            if id(m) in self._early_finished:
                continue
            m.decide_winner()
            await self._send(m.p1.id, s_round_end(
                m.winner.name if m.winner else "?",
                m.get_result(m.p1.id).to_dict(),
                m.get_result(m.p2.id).to_dict()))
            await self._send(m.p2.id, s_round_end(
                m.winner.name if m.winner else "?",
                m.get_result(m.p2.id).to_dict(),
                m.get_result(m.p1.id).to_dict()))
        self._early_finished.clear()
        self.log.emit(f"{name} 已结束")
        self.round_finished.emit(name)
        self.status.emit("等待下一赛程")

    async def _finish_current_round(self):
        self.log.emit("当前赛程已结束")
        self._manual_mode = False
        self.round_finished.emit(self._current_manual_round if hasattr(self, "_current_manual_round") else "手动结束")
        await self._broadcast(s_force_end("赛程结束"))

    async def _force_finish(self):
        """强制结束比赛：广播结束消息 + 发送当前对局结果 + 重置状态（不显示排名）"""
        await self._broadcast(s_force_end("管理员结束"))
        # 发送当前轮次结果给选手
        if hasattr(self, '_current_matches') and self._current_matches:
            for m in self._current_matches:
                if not m.finished:
                    m.decide_winner()
                await self._send(m.p1.id, s_round_end(
                    m.winner.name if m.winner else "?",
                    m.get_result(m.p1.id).to_dict(),
                    m.get_result(m.p2.id).to_dict()))
                await self._send(m.p2.id, s_round_end(
                    m.winner.name if m.winner else "?",
                    m.get_result(m.p2.id).to_dict(),
                    m.get_result(m.p1.id).to_dict()))
        self.status.emit("比赛结束")
        self.tournament.reset()
        self._paused = False
        self._force_ended = False
        self._current_matches = None

    def stop_server(self):
        self.running = False
        if self._loop:
            try:
                if self._loop.is_running():
                    for t in asyncio.all_tasks(self._loop):
                        t.cancel()
                    self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass


BASE_STYLE = "QWidget{background-color:#F0F2F5;color:#222;font-family:'Microsoft YaHei';}"




from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QListWidget,
    QInputDialog, QMessageBox, QLineEdit, QAbstractItemView,
    QMenu, QDialog, QGroupBox, QScrollArea, QCheckBox,
)
from PyQt6.QtGui import QFont, QKeyEvent, QColor, QBrush, QIcon


class MatchConfigDialog(QDialog):
    def __init__(self, player_count, players, current_text="", current_time=60, parent=None, show_cancel=True, alive_ids=None):
        super().__init__(parent)
        self.show_cancel = show_cancel
        self.players = players
        self.alive_ids = alive_ids or set(p["id"] for p in players)
        self.selected_players = set(p["id"] for p in players if p["id"] in self.alive_ids)
        self.selected_text = current_text
        self.selected_time = current_time
        self.setWindowTitle("比赛配置")
        self.setMinimumWidth(550)
        self.setStyleSheet(f"{BASE_STYLE}QDialog{{background:#F5F6FA;}}")
        self.use_pinyin = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel(f"📊 当前参赛人数：{len(self.selected_players)} / {len(self.players)}")
        header.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #1A1A2E; padding: 8px; background: #E8EAF0; border-radius: 6px;")
        layout.addWidget(header)

        # 时间设置
        time_group = QGroupBox("⏱️ 比赛时间设置")
        time_group.setStyleSheet("QGroupBox{font-weight:bold;padding-top:10px;}")
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("比赛时长(秒)："))
        self.time_input = QLineEdit(str(self.selected_time))
        self.time_input.setFixedWidth(80)
        self.time_input.setStyleSheet("padding:6px;border:1px solid #CCC;border-radius:4px;background:#FFF;")
        time_layout.addWidget(self.time_input)
        time_layout.addStretch()
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        # 拼音模式
        pinyin_group = QGroupBox("🔤 输入模式")
        pinyin_group.setStyleSheet("QGroupBox{font-weight:bold;padding-top:10px;}")
        pinyin_layout = QHBoxLayout()
        self.pinyin_check = QCheckBox("拼音模式（打拼音字母）")
        self.pinyin_check.setStyleSheet("QCheckBox{color:#1A1A2E;}")
        pinyin_layout.addWidget(self.pinyin_check)
        pinyin_layout.addStretch()
        pinyin_group.setLayout(pinyin_layout)
        layout.addWidget(pinyin_group)

        self.player_group = QGroupBox("👥 选手选择（默认全选）")
        self.player_group.setStyleSheet("QGroupBox{font-weight:bold;padding-top:10px;}")
        player_layout = QVBoxLayout()

        self.player_scroll = QScrollArea()
        self.player_scroll.setWidgetResizable(True)
        self.player_scroll.setMaximumHeight(160)
        self.player_scroll.setStyleSheet("QScrollArea{border:1px solid #D0D3D9;border-radius:4px;background:#FFF;}")

        self.player_widget = QWidget()
        self.player_vbox = QVBoxLayout(self.player_widget)
        self.player_vbox.setSpacing(4)
        self.player_checks = {}

        checkbox_style = '''
            QCheckBox {
                color: #1A1A2E;
                background-color: #F5F6FA;
                border: 1px solid #D0D3D9;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #888;
                background-color: #FFF;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:unchecked {
                background-color: #FFF;
                border: 2px solid #888;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #27AE60;
            }
        '''

        for p in self.players:
            is_alive = p["id"] in self.alive_ids
            cb = QCheckBox(f"{p['name']} ({p['id'][:8]}...)" + ("" if is_alive else " [已淘汰]"))
            cb.setChecked(is_alive)
            cb.setEnabled(is_alive)
            cb.setStyleSheet(checkbox_style)
            cb.stateChanged.connect(self._on_player_toggle)
            self.player_vbox.addWidget(cb)
            self.player_checks[p["id"]] = cb

        self.player_scroll.setWidget(self.player_widget)
        player_layout.addWidget(self.player_scroll)
        self.player_group.setLayout(player_layout)
        layout.addWidget(self.player_group)

        self.text_group = QGroupBox("📝 题目选择")
        self.text_group.setStyleSheet("QGroupBox{font-weight:bold;padding-top:10px;}")
        text_layout = QVBoxLayout()

        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumHeight(120)
        self.text_display.setFont(QFont("Microsoft YaHei", 11))
        self.text_display.setStyleSheet(
            "background:#FFF;color:#333;border:1px solid #D0D3D9;"
            "border-radius:4px;padding:8px;")
        if self.selected_text:
            self.text_display.setPlainText(self.selected_text)
        else:
            self.text_display.setPlainText("未选择题目（点击下方按钮选择）")
        text_layout.addWidget(self.text_display)

        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("📂 导入 TXT 文件")
        self.import_btn.setStyleSheet("QPushButton{padding:6px 12px;background:#3498DB;color:white;border:none;border-radius:4px;}")
        self.import_btn.clicked.connect(self._import_txt)

        self.input_btn = QPushButton("⌨️ 键盘输入")
        self.input_btn.setStyleSheet("QPushButton{padding:6px 12px;background:#27AE60;color:white;border:none;border-radius:4px;}")
        self.input_btn.clicked.connect(self._input_text)

        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.setStyleSheet("QPushButton{padding:6px 12px;background:#E74C3C;color:white;border:none;border-radius:4px;}")
        self.clear_btn.clicked.connect(self._clear_text)

        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.input_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        text_layout.addLayout(btn_row)
        self.text_group.setLayout(text_layout)
        layout.addWidget(self.text_group)

        self.info_label = QLabel("⚠️ 请先选择比赛题目")
        self.info_label.setStyleSheet("color:#E74C3C;padding:4px;")
        self.info_label.setVisible(False)
        layout.addWidget(self.info_label)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet("QPushButton{padding:8px;background:#95A5A6;color:white;border:none;border-radius:4px;}")
        cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = QPushButton("▶ 开始比赛")
        self.confirm_btn.setFixedWidth(120)
        self.confirm_btn.setStyleSheet("QPushButton{padding:8px;background:#27AE60;color:white;border:none;border-radius:4px;font-weight:bold;}")
        self.confirm_btn.clicked.connect(self._on_confirm)
        if self.show_cancel:
            btns.addWidget(cancel_btn)
        btns.addWidget(self.confirm_btn)
        layout.addLayout(btns)

    def _on_player_toggle(self):
        self.selected_players = {pid for pid, cb in self.player_checks.items() if cb.isChecked()}
        header = self.findChild(QLabel)
        if header:
            header.setText(f"📊 当前参赛人数：{len(self.selected_players)} / {len(self.players)}")

    def _import_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择题目文件", "", "文本(*.txt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    self.selected_text = content
                    self.text_display.setPlainText(content)
                    self.info_label.setVisible(False)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"读取文件失败：{e}")

    def _input_text(self):
        text, ok = QInputDialog.getMultiLineText(self, "输入题目", "输入比赛文本（50-80字）：")
        if ok and text.strip():
            self.selected_text = text.strip()
            self.text_display.setPlainText(self.selected_text)
            self.info_label.setVisible(False)

    def _clear_text(self):
        self.selected_text = ""
        self.text_display.setPlainText("未选择题目（点击下方按钮选择）")
        self.info_label.setVisible(False)

    def _on_confirm(self):
        if not self.selected_text.strip() and not self.pinyin_check.isChecked():
            self.info_label.setVisible(True)
            QMessageBox.warning(self, "提示", "请先选择比赛题目！")
            return
        self.use_pinyin = self.pinyin_check.isChecked()
        try:
            t = int(self.time_input.text().strip())
            self.selected_time = max(10, min(300, t))
        except ValueError:
            self.selected_time = 60
        self.accept()


class ServerGUI(QWidget):
    _PLAYER_HEADERS = ["选手名", "速度", "正确率", "状态"]
    _RANK_HEADERS = ["排名", "选手名", "得分"]

    def __init__(self):
        super().__init__()
        # 强制所有子控件继承 IME 支持，不限制输入法类型
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setWindowTitle("打字对战·服务端")
        self.setWindowIcon(get_safe_icon('server.ico'))
        self.resize(1150, 700)
        self.setMinimumSize(950, 580)
        self.server: GameServer | None = None
        self._player_data: dict[str, dict] = {}    # pid -> {name, speed, accuracy, status}
        self._player_row_map: dict[str, int] = {}  # pid -> table row
        self._rank_data: list[dict] = []
        self._build()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_player_table)
        self._refresh_timer.timeout.connect(self._refresh_rank_table)
        self._refresh_timer.start(500)
        # 启动遮罩层（必须按 "启动服务" 按钮才能取消）
        self._show_startup_overlay()
        # 支持中文输入法
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)

    # ---- event filter helpers ----

    def eventFilter(self, obj, event):
        if obj is self._startup_overlay and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._on_startup_confirm()
                return True
            if event.key() == Qt.Key.Key_Escape:
                QApplication.quit()
                return True
        return super().eventFilter(obj, event)

    def _btn(self, text, color, en=True):
        b = QPushButton(text)
        b.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        b.setMinimumHeight(38)
        b.setEnabled(en)
        b.setStyleSheet(
            f"QPushButton{{background:{color};color:white;border:none;border-radius:5px;padding:6px 18px;}}"
            f"QPushButton:hover{{opacity:0.85;}}"
            f"QPushButton:disabled{{background:#CCC;color:#999;}}")
        return b

    def _show_startup_overlay(self):
        """启动遮罩：全屏暗色遮罩 + 中部"启动服务"按钮，按下方可操作"""
        self._startup_overlay = QWidget(self)
        self._startup_overlay.setGeometry(0, 0, self.width(), self.height())
        self._startup_overlay.setStyleSheet("background-color: rgba(0,0,0,180);")
        self._startup_overlay.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._startup_overlay.setFocus()
        # Install event filter to capture keys even when other widgets have focus
        self._startup_overlay.installEventFilter(self)

        layout = QVBoxLayout(self._startup_overlay)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 标题
        title = QLabel("🖥  打字对战服务端")
        title.setFont(QFont("Microsoft YaHei", 36, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(title)

        subtitle = QLabel("按下方按钮启动服务，或按 Enter 键")
        subtitle.setFont(QFont("Microsoft YaHei", 16))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #CCC; background: transparent; margin-bottom: 40px;")
        layout.addWidget(subtitle)

        # 启动按钮
        start_btn = QPushButton("🚀  启 动 服 务")
        start_btn.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        start_btn.setFixedSize(320, 80)
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #27AE60, stop:1 #1E8449);
                color: white; border: none; border-radius: 16px;
                font-size: 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2ECC71, stop:1 #229954);
            }
            QPushButton:pressed { background: #1E8449; }
        """)
        start_btn.clicked.connect(self._on_startup_confirm)
        layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        hint_row = QHBoxLayout()
        hint_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("Enter 启动  |  F11 全屏  |  Esc 退出")
        hint.setFont(QFont("Microsoft YaHei", 12))
        hint.setStyleSheet("color: #888; background: transparent; margin-top: 30px;")
        hint_row.addWidget(hint)
        layout.addLayout(hint_row)

        self._startup_overlay.raise_()
        self._startup_overlay.show()

    def _on_startup_confirm(self):
        """点击启动按钮或按 Enter：隐藏遮罩 + 启动服务"""
        if self._startup_overlay:
            self._startup_overlay.removeEventFilter(self)
            self._startup_overlay.hide()
            self._startup_overlay.deleteLater()
            self._startup_overlay = None
        self._ts()

    def _build(self):
        m = QVBoxLayout(self)
        m.setContentsMargins(10, 10, 10, 10)
        m.setSpacing(10)

        # 顶部栏
        top = QHBoxLayout()
        top.setSpacing(10)
        t = QLabel("🖥 打字对战服务端")
        t.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        t.setStyleSheet("color:#222;")
        hint = QLabel("F11全屏 Esc退出")
        hint.setStyleSheet("color:#999;font-size:12px;")
        self.st = QLabel("未启动")
        self.st.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        self.st.setStyleSheet(
            "color:#555;background:#FFF;border:1px solid #D0D3D9;"
            "border-radius:8px;padding:10px 20px;")
        self.bs = QPushButton("🟢 启动")
        self.bs.setFont(QFont("Microsoft YaHei", 14))
        self.bs.setFixedSize(120, 45)
        self.bs.clicked.connect(self._ts)
        self.bs.setStyleSheet(
            "QPushButton{background:#2980B9;color:white;border:none;border-radius:8px;}"
            "QPushButton:hover{background:#1F6DA0;}"
            "QPushButton:pressed{background:#1A5A80;}")
        top.addWidget(t)
        top.addStretch()
        top.addWidget(hint)
        top.addSpacing(20)
        top.addWidget(self.st)
        top.addWidget(self.bs)
        m.addLayout(top)

        # 主体区域
        body = QHBoxLayout()
        body.setSpacing(15)

        # ---- 左侧区域 ----
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        # 选手状态卡片
        player_card = QFrame()
        player_card.setStyleSheet(
            "QFrame{background:white;border:1px solid #D0D3D9;"
            "border-radius:8px;}")
        player_card_layout = QVBoxLayout(player_card)
        player_card_layout.setSpacing(6)
        player_card_layout.setContentsMargins(12, 12, 12, 12)

        player_header = QLabel("🏅 选手状态")
        player_header.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        player_card_layout.addWidget(player_header)

        # 列说明栏
        player_info_bar = QLabel(
            "选手名  |  速度(字/分)  |  正确率  |  状态")
        player_info_bar.setFont(QFont("Microsoft YaHei", 10))
        player_info_bar.setStyleSheet(
            "color:#666;background:#F0F2F5;padding:4px 8px;"
            "border:1px solid #E0E3E8;border-radius:4px;")
        player_card_layout.addWidget(player_info_bar)

        # 选手表格
        self._player_table = QTableWidget()
        self._player_table.setColumnCount(4)
        self._player_table.setHorizontalHeaderLabels(self._PLAYER_HEADERS)
        self._player_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._player_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._player_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._player_table.setAlternatingRowColors(True)
        self._player_table.horizontalHeader().setStretchLastSection(True)
        self._player_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._player_table.setStyleSheet(
            "QTableWidget{background:white;border:1px solid #D0D3D9;"
            "border-radius:4px;gridline-color:#E8EAEE;}"
            "QTableWidget::item{padding:6px 8px;}"
            "QTableWidget::item:alternate{background:#F5F6FA;}"
            "QHeaderView::section{background:#E8EAF0;color:#333;"
            "padding:6px;border:none;font-weight:bold;}")
        player_card_layout.addWidget(self._player_table, stretch=1)
        left_panel.addWidget(player_card, stretch=2)

        # 题库区域（卡片式）
        tf = QFrame()
        tf.setStyleSheet(
            "QFrame{background:white;border:1px solid #D0D3D9;"
            "border-radius:8px;}")
        tfl = QVBoxLayout(tf)
        tfl.setSpacing(8)
        tfl.setContentsMargins(12, 12, 12, 12)
        th = QHBoxLayout()
        th_label = QLabel("📚 题库")
        th_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        th.addWidget(th_label)
        self.tc = QLabel("")
        self.tc.setStyleSheet("color:#888;font-size:11px;")
        th.addStretch()
        th.addWidget(self.tc)
        tfl.addLayout(th)
        self.tl = QListWidget()
        self.tl.setFont(QFont("Microsoft YaHei", 11))
        self.tl.setStyleSheet(
            "QListWidget{background:white;border:1px solid #D0D0D0;"
            "border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;}"
            "QListWidget::item:selected{background:#3498DB;color:white;}")
        tfl.addWidget(self.tl, stretch=1)
        tbr = QHBoxLayout()
        tbr.setSpacing(8)
        for txt, clr, fn in [
            ("导入TXT", "#3498DB", self._import),
            ("添加", "#27AE60", self._add_text),
            ("删除", "#E74C3C", self._del_text),
        ]:
            b = QPushButton(txt)
            b.setFont(QFont("Microsoft YaHei", 11))
            b.setMinimumHeight(32)
            b.setStyleSheet(
                f"QPushButton{{background:{clr};color:white;border:none;border-radius:6px;}}"
                f"QPushButton:hover{{opacity:0.9;}}")
            b.clicked.connect(fn)
            tbr.addWidget(b)
        tfl.addLayout(tbr)
        left_panel.addWidget(tf, stretch=1)

        body.addLayout(left_panel, stretch=1)

        # 中间控制按钮
        center_btns = QVBoxLayout()
        center_btns.setSpacing(15)
        center_btns.addStretch()
        self.bstart = self._btn("▶ 开始比赛", "#27AE60", False)
        self.bstart.clicked.connect(self._start)
        self.bpause = self._btn("⏸ 暂停", "#F39C12", False)
        self.bpause.clicked.connect(self._pause)
        self.bend = self._btn("⏹ 结束", "#E74C3C", False)
        self.bend.clicked.connect(self._end)
        center_btns.addWidget(self.bstart)
        center_btns.addWidget(self.bpause)
        center_btns.addWidget(self.bend)
        self.bexport = self._btn("📤 导出排名", "#8E44AD", False)
        self.bexport.clicked.connect(self._export_ranking)
        center_btns.addWidget(self.bexport)
        center_btns.addStretch()
        body.addLayout(center_btns)

        # 右侧区域
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # 实时排行（卡片式）
        rank_card = QFrame()
        rank_card.setStyleSheet(
            "QFrame{background:white;border:1px solid #D0D3D9;"
            "border-radius:8px;}")
        rank_card_layout = QVBoxLayout(rank_card)
        rank_card_layout.setSpacing(6)
        rank_card_layout.setContentsMargins(12, 12, 12, 12)

        rank_header = QLabel("🏆 实时排行")
        rank_header.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        rank_card_layout.addWidget(rank_header)

        # 列说明栏
        rank_info_bar = QLabel(
            "排名  |  选手名  |  得分")
        rank_info_bar.setFont(QFont("Microsoft YaHei", 10))
        rank_info_bar.setStyleSheet(
            "color:#666;background:#F0F2F5;padding:4px 8px;"
            "border:1px solid #E0E3E8;border-radius:4px;")
        rank_card_layout.addWidget(rank_info_bar)

        # 排名表格
        self._rank_table = QTableWidget()
        self._rank_table.setColumnCount(3)
        self._rank_table.setHorizontalHeaderLabels(self._RANK_HEADERS)
        self._rank_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._rank_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rank_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._rank_table.setAlternatingRowColors(True)
        self._rank_table.horizontalHeader().setStretchLastSection(True)
        self._rank_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._rank_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._rank_table.setStyleSheet(
            "QTableWidget{background:white;border:1px solid #D0D3D9;"
            "border-radius:4px;gridline-color:#E8EAEE;}"
            "QTableWidget::item{padding:6px 8px;}"
            "QTableWidget::item:alternate{background:#F5F6FA;}"
            "QHeaderView::section{background:#E8EAF0;color:#333;"
            "padding:6px;border:none;font-weight:bold;}")

        # 排名表格右键菜单：复制选手名
        self._rank_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._rank_table.customContextMenuRequested.connect(self._on_rank_table_context_menu)

        rank_card_layout.addWidget(self._rank_table, stretch=1)
        right_panel.addWidget(rank_card, stretch=1)

        # 赛事日志（卡片式）
        log_card = QFrame()
        log_card.setStyleSheet(
            "QFrame{background:white;border:1px solid #D0D3D9;"
            "border-radius:8px;}")
        log_card_layout = QVBoxLayout(log_card)
        log_card_layout.setSpacing(6)
        log_card_layout.setContentsMargins(12, 12, 12, 12)

        log_label = QLabel("📋 赛事日志")
        log_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        log_card_layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Microsoft YaHei", 11))
        self.log.setStyleSheet(
            "QTextEdit{background:#2A2A3E;color:#E8E8E8;"
            "border:1px solid #404060;border-radius:6px;padding:10px;}"
        )
        self.log.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        log_card_layout.addWidget(self.log, stretch=1)
        right_panel.addWidget(log_card, stretch=2)

        body.addLayout(right_panel, stretch=1)

        m.addLayout(body, stretch=1)

    def _ts(self):
        if self.server and self.server.running:
            self._log("停止中...")
            self.server.running = False
            if self.server._loop and self.server._loop.is_running():
                def _s():
                    # 先关闭 UDP transport 释放端口
                    if self.server._udp_transport and not self.server._udp_transport.is_closing():
                        self.server._udp_transport.close()
                    # 取消所有任务让 event loop 自然结束
                    for t in asyncio.all_tasks(self.server._loop):
                        t.cancel()
                self.server._loop.call_soon_threadsafe(_s)
            self.server.quit()
            self.server.wait(3000)
            # 确保关闭 event loop
            if self.server._loop and not self.server._loop.is_closed():
                try:
                    self.server._loop.close()
                except Exception:
                    pass
            self.server = None
            self.bs.setText("🟢 启动")
            self.st.setText("未启动")
            self.bstart.setEnabled(False)
            self.bpause.setEnabled(False)
            self.bend.setEnabled(False)
            # 清空选手和排行榜
            self._player_table.setRowCount(0)
            self._rank_table.setRowCount(0)
            self._player_data.clear()
            self._player_row_map.clear()
            self._rank_data.clear()
        else:
            self._log("启动中...")
            self.server = GameServer()
            self.server.log.connect(self._log)
            self.server.players_changed.connect(self._on_players)
            self.server.matches_update.connect(self._on_matches)
            self.server.ranking_ready.connect(self._on_ranking)
            self.server.status.connect(lambda s: self.st.setText(s))
            self.server.progress.connect(self._on_progress)
            self.server.player_status.connect(self._on_player_status)
            self.server.round_finished.connect(self._on_round_finished)
            self.server.start()
            self.bs.setText("🔴 停止")
            self.st.setText("🟢 运行中")
            self.bstart.setEnabled(True)
            self.bpause.setEnabled(False)
            self.bend.setEnabled(False)

    def _start(self):
        if self.server and self.server._loop:
            if not self.server.tournament.player_list():
                QMessageBox.warning(self, "提示", "当前没有选手！")
                return
            if self.server.tournament.alive:
                QMessageBox.warning(self, "提示", "比赛正在进行中！")
                return
            # 清空上一把的实时排行和选手状态
            self._rank_data = []
            self._rank_table.setRowCount(0)
            for pid in self._player_data:
                self._player_data[pid]["speed"] = "--"
                self._player_data[pid]["accuracy"] = "--"
                self._player_data[pid]["status"] = "等待中"
            self._refresh_player_table()
            players = self.server.tournament.player_list()
            if self.tl.currentRow() < 0 and self.server and self.server.tm.count() > 0:
                self.tl.setCurrentRow(0)
            current_text = ""
            if self.tl.currentRow() >= 0 and self.server:
                current_text = self.server.tm.get_all()[self.tl.currentRow()]
            dialog = MatchConfigDialog(len(players), players, current_text, self.server.time_limit, self,
                                       alive_ids={p["id"] for p in players})
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            self._current_text = dialog.selected_text
            use_pinyin = dialog.use_pinyin
            t = dialog.selected_time
            self.server.time_limit = t
            mode = "拼音" if use_pinyin else "汉字"
            self._log(f"开始比赛({t}秒, {mode}模式)...")
            self.bstart.setEnabled(False)
            self.bpause.setEnabled(True)
            self.bend.setEnabled(True)
            self.server._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self.server._run_tournament(self._current_text, use_pinyin)))

    def _pause(self):
        if self.server:
            self.server._paused = not self.server._paused
            self._log("暂停" if self.server._paused else "恢复")
            self.bpause.setText("▶ 恢复" if self.server._paused else "⏸ 暂停")
            if self.server._loop:
                rm = self.server._match_remaining
                if self.server._paused:
                    self.server._loop.call_soon_threadsafe(
                        lambda: asyncio.ensure_future(
                            self.server._broadcast(s_pause_broadcast(int(rm * 1000)))))
                else:
                    self.server._loop.call_soon_threadsafe(
                        lambda: asyncio.ensure_future(
                            self.server._broadcast(s_resume_broadcast(int(rm * 1000)))))

    def _end(self):
        if self.server and self.server._loop:
            self._log("强制结束")
            self.server._force_ended = True
            self.server._match_remaining = 0
            # 在事件循环中执行：广播结束 + 计算排名
            self.server._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self.server._force_finish()))
            self.bpause.setEnabled(False)
            self.bend.setEnabled(False)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入", "", "文本(*.txt);;所有(*.*)")
        if path and self.server:
            n = self.server.tm.import_txt(path)
            self._log(f"导入{n}段")
            self._rt()

    def _add_text(self):
        if not self.server:
            return
        t, ok = QInputDialog.getMultiLineText(self, "添加", "输入文本(50-80字):")
        if ok and t.strip():
            if self.server.tm.add_text(t.strip()):
                self._log("已添加")
                self._rt()
            else:
                QMessageBox.warning(self, "提示", "文本不符合要求(50-80字符)")

    def _del_text(self):
        if not self.server:
            return
        r = self.tl.currentRow()
        if r >= 0:
            self.server.tm.remove_text(r)
            self._rt()

    def _rt(self):
        if not self.server:
            return
        self.tl.clear()
        for t in self.server.tm.get_all():
            self.tl.addItem(t[:60] + "..." if len(t) > 60 else t)
        self.tc.setText(f"{self.server.tm.count()}段")

    def _kick_player(self, pid, name):
        if not self.server or not self.server._loop:
            return
        self.server._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self.server.kick_player(pid, "管理员踢出")))
        self._log(f"[{datetime.now().strftime('%H:%M:%S')}] 选手 {name} 已退出比赛")

    def _log(self, msg):
        if not msg.startswith("["):
            timestamped = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        else:
            timestamped = msg
        self.log.append(timestamped)
        try:
            logger = get_logger("server")
            logger.info(msg)
        except Exception:
            pass

    # ---- 选手表格 ----

    def _on_players(self, c, pl):
        self._log(f"选手更新:{c}人")
        self._player_table.setRowCount(len(pl))
        self._player_row_map.clear()
        for row, p in enumerate(pl):
            pid = p["id"]
            self._player_row_map[pid] = row
            self._player_data[pid] = {
                "name": p["name"],
                "speed": "--",
                "accuracy": "--",
                "status": "等待中",
            }
            name_item = QTableWidgetItem(p["name"])
            name_item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._player_table.setItem(row, 0, name_item)
            self._player_table.setItem(row, 1, QTableWidgetItem("--"))
            self._player_table.setItem(row, 2, QTableWidgetItem("--"))
            status_item = QTableWidgetItem("等待中")
            status_item.setForeground(QBrush(QColor("#95A5A6")))
            self._player_table.setItem(row, 3, status_item)
        self.bstart.setEnabled(c >= 2)
        if self.server:
            self._rt()

    def _on_matches(self, rn, ms):
        for m in ms:
            self._log(f"  {m.p1.name} vs {m.p2.name}")
            for pid in (m.p1.id, m.p2.id):
                if pid in self._player_data:
                    self._player_data[pid]["speed"] = "--"
                    self._player_data[pid]["accuracy"] = "--"
                    self._player_data[pid]["status"] = "比赛中"
        self._refresh_player_table()

    def _on_round_finished(self, round_name: str):
        """一轮结束后弹出比赛配置，让管理员手动开始下一轮"""
        if not self.server:
            return
        # 手动赛程（_start_round）不接管
        if self.server._manual_mode:
            return
        if not self.server.tournament.can_continue():
            self.server._finish_tournament()
            self._log("比赛全部结束!")
            return
        self._log(f"{round_name} 已结束，请配置下一轮")
        # 仅显示存活选手
        alive_players = [p.to_dict() for p in self.server.tournament.alive]
        current_text = ""
        if self.tl.currentRow() >= 0 and self.server:
            current_text = self.server.tm.get_all()[self.tl.currentRow()]
        alive_ids = {p.id for p in self.server.tournament.alive}
        all_players = self.server.tournament.player_list()
        dialog = MatchConfigDialog(
            len(all_players), all_players, current_text,
            self.server.time_limit, self, show_cancel=False,
            alive_ids=alive_ids)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            # 管理员取消 → 结算比赛
            self.server._finish_tournament()
            return
        # 开始下一轮
        self._current_text = dialog.selected_text
        use_pinyin = dialog.use_pinyin
        self.server.time_limit = dialog.selected_time
        self.server._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                self.server._run_one_round(self._current_text, use_pinyin)))

    def _on_progress(self, name, speed, acc, status):
        for pid, data in self._player_data.items():
            if data["name"] == name:
                data["speed"] = speed
                data["accuracy"] = acc
                data["status"] = "比赛中"
                break

    def _refresh_player_table(self):
        for pid, data in self._player_data.items():
            row = self._player_row_map.get(pid)
            if row is None:
                continue
            name = data["name"]
            # Speed
            speed_text = data.get("speed", "--")
            if speed_text and speed_text != "--":
                try:
                    cps = float(speed_text)
                    cpm = int(cps * 60)
                    speed_display = f"{cpm}字/分"
                except (ValueError, TypeError):
                    speed_display = "--"
            else:
                speed_display = "--"
            spd_item = self._player_table.item(row, 1)
            if spd_item:
                spd_item.setText(speed_display)

            # Accuracy
            acc_text = data.get("accuracy", "--")
            if acc_text and acc_text != "--":
                acc_display = f"{acc_text}"
            else:
                acc_display = "--"
            acc_item = self._player_table.item(row, 2)
            if acc_item:
                acc_item.setText(acc_display)

            # Status
            status = data.get("status", "等待中")
            if status == "比赛中":
                status_display = "比赛中"
                color = QColor("#27AE60")
            elif status.startswith("#"):
                status_display = "已结束"
                color = QColor("#3498DB")
            else:
                status_display = "等待中"
                color = QColor("#95A5A6")
            status_item = self._player_table.item(row, 3)
            if status_item:
                status_item.setText(status_display)
                status_item.setForeground(QBrush(color))
                font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
                if status == "比赛中":
                    pass
                status_item.setFont(font)

    # ---- 排名表格 ----

    def _on_rank_table_context_menu(self, pos):
        item = self._rank_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        name_item = self._rank_table.item(row, 1)
        if not name_item:
            return
        player_name = name_item.text()
        menu = QMenu(self)
        copy_action = menu.addAction(f"复制选手名: {player_name}")
        action = menu.exec(self._rank_table.viewport().mapToGlobal(pos))
        if action == copy_action:
            clipboard = QApplication.clipboard()
            clipboard.setText(player_name)
            self._log(f"已复制选手名: {player_name}")

    def _on_player_status(self, pid: str, status_text: str):
        if pid in self._player_data:
            self._player_data[pid]["status"] = status_text
        self._refresh_player_table()

    def _export_ranking(self):
        """导出最终排名为 TXT 文件"""
        if not self._rank_data:
            QMessageBox.information(self, "提示", "暂无排名数据可导出")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出排名", "最终排名.txt", "文本(*.txt)")
        if not path:
            return
        try:
            now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            lines = [f"=== 打字对战 最终排名 ===",
                     f"导出时间: {now}",
                     f"总人数: {len(self._rank_data)}",
                     "-" * 40]
            for item in self._rank_data:
                lines.append(f"{item['rank']:>3}. {item['name']:<12} {item['score']:>6}分  "
                             f"完成率:{item['completion']:>5}%  正确率:{item['accuracy']:>5}%")
            lines.append("-" * 40)
            lines.append("")
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            self._log(f"排名已导出: {path}")
            QMessageBox.information(self, "导出成功", f"排名已保存至:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _on_ranking(self, r):
        self._rank_data = list(r)
        self.bexport.setEnabled(True)
        self._rank_table.setRowCount(len(r))
        for row, item in enumerate(r):
            rank_text = str(item["rank"])
            if item["rank"] == 1:
                rank_text = f"🥇 {item['rank']}"
            elif item["rank"] == 2:
                rank_text = f"🥈 {item['rank']}"
            elif item["rank"] == 3:
                rank_text = f"🥉 {item['rank']}"

            rank_item = QTableWidgetItem(rank_text)
            rank_item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rank_table.setItem(row, 0, rank_item)

            name_item = QTableWidgetItem(item["name"])
            name_item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            self._rank_table.setItem(row, 1, name_item)

            score_item = QTableWidgetItem(f"{item['score']}分")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rank_table.setItem(row, 2, score_item)

        self._log("\n=== 最终排名 ===")
        for item in r:
            self._log(f"  {item['rank']:2d}. {item['name']}  {item['score']}分")
            for pid, data in self._player_data.items():
                if data["name"] == item["name"]:
                    data["status"] = f"#{item['rank']}"
        self._refresh_player_table()
        self.bstart.setEnabled(True)
        self.bpause.setEnabled(False)
        self.bend.setEnabled(False)

    def _refresh_rank_table(self):
        if not self._rank_data:
            return
        self._rank_table.setRowCount(len(self._rank_data))
        for row, item in enumerate(self._rank_data):
            rank_text = str(item["rank"])
            if item["rank"] == 1:
                rank_text = f"🥇 {item['rank']}"
            elif item["rank"] == 2:
                rank_text = f"🥈 {item['rank']}"
            elif item["rank"] == 3:
                rank_text = f"🥉 {item['rank']}"

            rank_item = self._rank_table.item(row, 0)
            if rank_item:
                rank_item.setText(rank_text)
            else:
                rank_item = QTableWidgetItem(rank_text)
                rank_item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
                rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._rank_table.setItem(row, 0, rank_item)

            name_item = self._rank_table.item(row, 1)
            if not name_item:
                name_item = QTableWidgetItem(item["name"])
                name_item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
                self._rank_table.setItem(row, 1, name_item)

            score_item = self._rank_table.item(row, 2)
            if score_item:
                score_item.setText(f"{item['score']}分")
            else:
                score_item = QTableWidgetItem(f"{item['score']}分")
                score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._rank_table.setItem(row, 2, score_item)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif e.key() == Qt.Key.Key_Escape:
            r = QMessageBox.question(
                self, "退出", "确定退出?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                if self.server:
                    self.server.running = False
                    try:
                        self.server.quit()
                        self.server.wait(2000)
                    except Exception:
                        pass
                QApplication.quit()
        else:
            super().keyPressEvent(e)


if __name__ == "__main__":
    sys.excepthook = global_exception_handler
    try:
        setup_logger("server", "server")
        logger = get_logger("server")
        logger.info("打字对战服务端启动")
    except Exception as e:
        print(f"初始化日志失败: {e}")
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet(BASE_STYLE)
        w = ServerGUI()
        w.show()
        sys.exit(app.exec())
    except Exception as e:
        try:
            logger = get_logger("server")
            logger.critical("主程序异常退出", exc_info=True)
        except Exception:
            pass
        raise
