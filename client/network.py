"""WebSocket客户端 — v4 协议 + 可靠服务器发现 + 日志集成 + 击键批处理"""

import asyncio
import json
import socket
import time
import re
import sys
import os
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal

from common.logger import get_logger

from common.protocol import (
    encode, decode,
    C_JOIN, C_PROGRESS, C_PONG,
    C_RECONNECT, C_READY,
    S_JOIN_ACK, S_PLAYER_LIST, S_MATCH_BEGIN, S_ROUND_END,
    S_FINAL_RANKING, S_COUNTDOWN, S_FORCE_END,
    S_ERROR, S_PING,
    S_PAUSE_BROADCAST, S_RESUME_BROADCAST,
    S_TIME_SYNC, S_READY_STATUS, S_FULL_STATE,
)

UDP_PORT = 23333
DISCOVER_MAGIC = b"type_battle_discover"
BROADCAST_PREFIX = "TYPING_SERVER:"


class GameClient(QThread):
    connected = pyqtSignal(dict)
    auth_failed = pyqtSignal(str)
    player_update = pyqtSignal(list)
    match_begin = pyqtSignal(dict)
    round_end = pyqtSignal(dict)
    tournament_over = pyqtSignal(list)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    server_found = pyqtSignal(str, int)
    force_end = pyqtSignal(str)
    walkover = pyqtSignal()
    countdown_signal = pyqtSignal(int)
    time_sync = pyqtSignal(int, bool)
    pause_broadcast = pyqtSignal(int)
    resume_broadcast = pyqtSignal(int)
    full_state = pyqtSignal(dict)
    manual_ip_requested = pyqtSignal()
    connection_lost = pyqtSignal(str)
    reconnected = pyqtSignal()


    def __init__(self):
        super().__init__()
        self._ws = None
        self._loop = None
        self._pid = ""
        self._running = False
        self._host = None
        self._port = 8888
        self._reconnecting = False
        self._reconnect_name = ""
        self._reconnect_handled = False  # 防止断开后死循环重连
        self._last_pong_time = 0.0
        # ── 击键批处理 ──
        self._batch_timer_handle = None
        self.logger = get_logger("client")

    def set_server(self, host, port):
        self._host = host
        self._port = port

    def run(self):
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())

    async def _connect(self):
        if not self._host:
            await self._discover()
            if not self._host:
                self.error.emit("未找到服务器，请手动输入IP")
                return
        await self._connect_to_server()

    async def _connect_to_server(self):
        import websockets
        uri = f"ws://{self._host}:{self._port}"
        self.status.emit(f"连接 {uri}...")
        self.logger.info(f"正在连接服务器: {uri}")
        try:
            self._ws = await websockets.connect(uri, ping_interval=None)
        except (OSError, ConnectionRefusedError) as e:
            self.logger.exception(f"连接失败: {e}")
            if self._reconnecting:
                raise
            self.error.emit(f"连接失败: {e}")
            self.log_discovery(f"连接失败: {e}")
            return
        except Exception as e:
            self.logger.exception(f"连接失败: {e}")
            if self._reconnecting:
                raise
            self.error.emit(f"连接失败: {e}")
            self.log_discovery(f"连接失败: {e}")
            return

        self.status.emit("已连接")
        self.log_discovery(f"成功连接到服务器 {self._host}:{self._port}")
        self.logger.info(f"已连接到服务器 {self._host}:{self._port}")
        self._last_pong_time = time.time()

        async def ping_loop():
            while self._running and self._ws:
                try:
                    await asyncio.sleep(5)
                    if not self._ws or not self._running:
                        break
                    pong_waiter = await self._ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=15)
                    self._last_pong_time = time.time()
                    self.logger.debug("收到Pong")
                except asyncio.TimeoutError:
                    self.logger.warning("Ping超时，15秒未收到Pong")
                    break
                except websockets.exceptions.ConnectionClosed:
                    self.logger.warning("Ping时连接已关闭")
                    break
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.warning(f"Ping异常: {e}")
                    break

        ping_task = asyncio.create_task(ping_loop())

        try:
            async for raw in self._ws:
                if not self._running:
                    break
                try:
                    msg = decode(raw)
                    if msg is not None:
                        self._on_message(msg)
                except Exception as e:
                    self.logger.exception(f"处理消息时异常: {e}")
        except websockets.exceptions.ConnectionClosed as e:
            self.logger.warning(f"WebSocket连接关闭: {e}")
        except Exception as e:
            self.logger.exception(f"消息循环异常: {e}")
        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

        # 防止死循环：_reconnect() 失败后 _reconnecting 变回 False，
        # 不加此守卫会导致原地再次调用 _handle_disconnect 无限循环
        if self._running and not self._reconnecting and not self._reconnect_handled:
            self._reconnect_handled = True
            await self._handle_disconnect()

    async def _handle_disconnect(self):
        self.logger.info("连接断开，开始重连...")
        self.status.emit("连接断开，正在重连...")
        await self._reconnect()

    async def _reconnect(self):
        self._reconnecting = True
        try:
            intervals = [2, 3, 5]
            for i, delay in enumerate(intervals):
                if not self._running:
                    return
                self.logger.info(f"重连尝试 {i+1}/3，等待{delay}秒...")
                self.status.emit(f"重连中 ({i+1}/3)...")
                await asyncio.sleep(delay)
                try:
                    await self._connect_to_server()
                    self.reconnected.emit()
                    self.logger.info("重连成功")
                    if self._pid:
                        self.logger.info(f"重连后发送重连请求: player_id={self._pid}")
                        await asyncio.sleep(0.5)
                        asyncio.run_coroutine_threadsafe(
                            self._ws.send(encode({"t": C_RECONNECT, "p": self._pid})),
                            self._loop
                        )
                    elif self._reconnect_name:
                        self.logger.info(f"重连后重新认证: name={self._reconnect_name}")
                        await asyncio.sleep(0.5)
                        asyncio.run_coroutine_threadsafe(
                            self._ws.send(encode({"t": C_JOIN, "n": self._reconnect_name})),
                            self._loop
                        )
                    return
                except Exception as e:
                    self.logger.warning(f"重连失败 ({i+1}/3): {e}")
                    await asyncio.sleep(0.5)
            if self._running:
                self.logger.error("重连全部失败")
                self.connection_lost.emit("与服务器失去连接，已重试3次仍失败")
        finally:
            self._reconnecting = False

    def log_discovery(self, msg: str):
        self.status.emit(f"[发现] {msg}")
        self.logger.debug(f"[发现] {msg}")

    def _is_valid_ip(self, ip: str) -> bool:
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, ip):
            return False
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)

    def _parse_server_broadcast(self, data: bytes) -> tuple:
        try:
            msg = data.decode('utf-8', errors='ignore')
            if msg.startswith(BROADCAST_PREFIX):
                parts = msg[len(BROADCAST_PREFIX):].split(':')
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    port = int(parts[1].strip())
                    return (ip, port)
        except Exception:
            pass
        return (None, None)

    async def _discover(self):
        loop = asyncio.get_event_loop()
        self.log_discovery("开始搜索服务器...")
        self.logger.info("开始自动发现服务器")

        for attempt in range(3):
            self.log_discovery(f"发现尝试 {attempt + 1}/3")
            self.logger.debug(f"发现尝试 {attempt + 1}/3")
            server_ip, server_port = await self._send_discover_once(loop)
            if server_ip:
                self._host = server_ip
                self._port = server_port
                self.log_discovery(f"发现服务器: {server_ip}:{server_port}")
                self.logger.info(f"发现服务器: {server_ip}:{server_port}")
                return
            if attempt < 2:
                self.log_discovery(f"未收到回复，等待1秒后重试...")
                self.logger.debug("等待1秒后重试")
                await asyncio.sleep(1.0)

        self.log_discovery("自动发现失败，提示手动输入IP...")
        self.logger.warning("自动发现失败")
        await self._show_manual_ip_dialog()

    async def _send_discover_once(self, loop) -> tuple:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1.0)
            sock.bind(('0.0.0.0', 0))

            sock.sendto(DISCOVER_MAGIC, ('255.255.255.255', UDP_PORT))
            self.log_discovery("已发送发现请求")
            self.logger.debug("发送UDP发现请求到 255.255.255.255:23333")

            data, addr = sock.recvfrom(1024)
            ip, port = self._parse_server_broadcast(data)
            if ip:
                self.log_discovery(f"收到来自 {addr[0]} 的广播: {ip}:{port}")
                self.logger.debug(f"收到服务器广播: {data}")
                return (ip, port or 8888)

        except socket.timeout:
            self.log_discovery("等待回复超时")
            self.logger.debug("UDP等待超时")
        except socket.error as e:
            self.log_discovery(f"Socket错误: {e}")
            self.logger.exception(f"Socket错误: {e}")
        except Exception as e:
            self.log_discovery(f"UDP错误: {e}")
            self.logger.exception(f"UDP发现异常: {e}")
        finally:
            if sock:
                sock.close()
        return (None, None)

    async def _show_manual_ip_dialog(self):
        self._manual_ip_future = asyncio.get_event_loop().create_future()
        self.manual_ip_requested.emit()
        try:
            ip, port = await asyncio.wait_for(self._manual_ip_future, timeout=120)
            self._host = ip
            self._port = port
            self.log_discovery(f"用户输入: {ip}:{port}")
            self.logger.info(f"用户输入IP: {ip}:{port}")
            await self._connect_to_server()
        except asyncio.TimeoutError:
            self.log_discovery("用户取消手动输入")
            self.logger.info("用户取消了手动输入IP")
            self.error.emit("已取消连接")
        except asyncio.exceptions.CancelledError:
            self.log_discovery("用户取消手动输入")
            self.logger.info("用户取消了手动输入IP")
            self.error.emit("已取消连接")
        except Exception as e:
            self.logger.exception(f"手动输入IP异常: {e}")
            self.error.emit(f"连接失败: {e}")

    def set_manual_ip(self, ip, port):
        if hasattr(self, '_manual_ip_future') and self._manual_ip_future and not self._manual_ip_future.done():
            self._loop.call_soon_threadsafe(self._manual_ip_future.set_result, (ip, port))

    def cancel_manual_ip(self):
        if hasattr(self, '_manual_ip_future') and self._manual_ip_future and not self._manual_ip_future.done():
            self._loop.call_soon_threadsafe(self._manual_ip_future.cancel)

    def _on_message(self, msg: dict):
        if msg is None:
            return
        t = msg.get("t", "")
        self.logger.debug(f"收到消息: type={t}")
        if t == S_JOIN_ACK:
            self._pid = msg["p"]
            self.connected.emit(msg)
        elif t == S_PLAYER_LIST:
            self.player_update.emit(msg.get("p", []))
        elif t == S_COUNTDOWN:
            self.countdown_signal.emit(msg.get("s", 5))
        elif t == S_MATCH_BEGIN:
            self.match_begin.emit(msg)
        elif t == S_ROUND_END:
            mr = msg.get("r1", {})
            if not msg.get("w") and mr.get("score") == 100 and mr.get("elapsed") == 0:
                self.walkover.emit()
            else:
                self.round_end.emit(msg)
        elif t == S_FINAL_RANKING:
            self.tournament_over.emit(msg.get("r", []))
            self.force_end.emit(msg.get("r", "管理员结束"))
        elif t == S_TIME_SYNC:
            self.time_sync.emit(msg.get("r", 0), msg.get("p", False))
        elif t == S_PAUSE_BROADCAST:
            self.pause_broadcast.emit(msg.get("r", 0))
        elif t == S_RESUME_BROADCAST:
            self.resume_broadcast.emit(msg.get("r", 0))
        elif t == S_FULL_STATE:
            self.full_state.emit(msg)
        elif t == S_READY_STATUS:
            pass
        elif t == S_ERROR:
            err_msg = msg.get("m", "")
            self.logger.warning(f"服务器错误: {err_msg}")
            self.error.emit(err_msg)
        elif t == S_PING:
            server_time = msg.get("s", 0)
            self.logger.debug(f"收到PING: server_time={server_time}")
            if self._ws and self._loop:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self._ws.send(encode({
                            "t": "o",
                            "ct": time.time(),
                            "st": server_time
                        })),
                        self._loop
                    )
                except Exception as e:
                    self.logger.warning(f"发送PONG失败: {e}")

    def _send(self, data: dict):
        self.logger.debug(f"发送消息: {data.get('t', '')}")
        if self._ws and self._loop and self._running:
            try:
                asyncio.run_coroutine_threadsafe(self._ws.send(encode(data)), self._loop)
            except Exception as e:
                self.logger.exception(f"发送消息失败: {e}")

    # ── 击键批处理 ──────────────────────────────────────────

    def send_progress(self, c, e, t):
        self._send({"t": C_PROGRESS, "c": c, "e": e, "l": t})

    def send_reconnect(self):
        self.logger.info(f"发送重连请求: pid={self._pid}")
        self._send({"t": C_RECONNECT, "p": self._pid})

    def send_ready(self):
        self._send({"t": C_READY, "r": True})

    def auth(self, name: str):
        self._reconnect_name = name
        self.logger.info(f"发送身份验证: name={name}")
        self._send({"t": C_JOIN, "n": name})

    def stop(self):
        self._running = False
        if self._batch_timer_handle:
            try:
                self._batch_timer_handle.cancel()
            except Exception:
                pass
        self.logger.info("停止客户端连接")
        if self._ws and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            except Exception:
                pass
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
