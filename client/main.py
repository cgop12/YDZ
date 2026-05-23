"""客户端入口 — QStackedWidget 页面管理 + 网络 + 日志 + 闪退防护"""

import sys, os, traceback
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QIcon

# 资源路径适配 PyInstaller --onefile
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
    _APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _APP_DIR = os.path.dirname(_BASE)

# 添加项目根目录到 path，用于导入 common 模块
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from common.logger import setup_logger, get_logger
from network import GameClient


def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        return os.path.dirname(os.path.abspath(__file__))


def get_safe_icon(icon_filename: str) -> QIcon:
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_path, icon_filename)
    return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()


def global_exception_handler(exc_type, exc_value, exc_tb):
    base_dir = get_app_base_dir()
    logs_dir = os.path.join(base_dir, "logs")
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except Exception:
        pass

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_file = os.path.join(logs_dir, f"crash_client_{timestamp}.log")

    try:
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write("=== 打字对战客户端崩溃日志 ===\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 60 + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            f.write("-" * 60 + "\n")
    except Exception as e:
        print(f"无法写入崩溃日志: {e}")

    try:
        logger = get_logger("client")
        logger.critical("客户端发生崩溃", exc_info=(exc_type, exc_value, exc_tb))
    except Exception:
        pass

    try:
        QTimer.singleShot(0, lambda: QMessageBox.critical(
            None, "客户端异常",
            f"客户端发生异常，已记录崩溃日志:\n{crash_file}"
        ))
    except Exception:
        pass

    if sys.__excepthook__ is not None:
        sys.__excepthook__(exc_type, exc_value, exc_tb)


from widgets import BASE_STYLE
from pages.login import LoginPage
from pages.lobby import LobbyPage
from pages.battle import BattlePage
from pages.result import ResultPage
from pages.waiting import WaitingPage
from pages.overlay import MessageOverlay
# ─── 页面索引常量 ───
PAGE_LOGIN   = 0
PAGE_LOBBY   = 1
PAGE_BATTLE  = 2
PAGE_RESULT  = 3
PAGE_WAITING = 4


class MainWindow(QWidget):
    def __init__(self, auto_name=None, auto_host=None, auto_port=None):
        super().__init__()
        # 强制所有子控件继承 IME 支持，不限制输入法类型
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setWindowTitle("打字对战")
        self.setWindowIcon(get_safe_icon('client.ico'))
        self.resize(1100, 750)
        self.setStyleSheet(BASE_STYLE)

        # ── 网络客户端 ──
        self.client = GameClient()

        # ── 页面 ──
        self.login  = LoginPage(self._on_connect)
        self.lobby  = LobbyPage()
        self.battle = BattlePage()
        self.result = ResultPage(on_back_to_lobby=self._on_back_to_lobby)
        self.waiting = WaitingPage()

        # ── QStackedWidget ──
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self.login)   # 0 PAGE_LOGIN
        self._stack.addWidget(self.lobby)   # 1 PAGE_LOBBY
        self._stack.addWidget(self.battle)  # 2 PAGE_BATTLE
        self._stack.addWidget(self.result)  # 3 PAGE_RESULT
        self._stack.addWidget(self.waiting) # 4 PAGE_WAITING
        self._stack.setCurrentIndex(PAGE_LOGIN)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        # ── 断连遮罩层 ──
        self.disconnect_overlay = None

        # ── 连接信号 ──
        self._wire()
        self.battle.on_progress  = self._on_progress

        self._fullscreen = False

        # auto-join via CLI args
        if auto_name:
            QTimer.singleShot(500, lambda: self._on_connect(
                auto_name, auto_host or None, auto_port if auto_host else None))

    # ── 页面切换 ──────────────────────────────────────────────────
    def _switch(self, page_idx: int):
        self._stack.setCurrentIndex(page_idx)

    # ── 信号连接 ──────────────────────────────────────────────────
    def _wire(self):
        self.client.connected.connect(self._on_connected)
        self.client.auth_failed.connect(self.login.set_status)
        self.client.player_update.connect(self.lobby.update_players)
        self.client.match_begin.connect(self._on_match_begin)
        self.client.round_end.connect(self._on_round_end)
        self.client.tournament_over.connect(self._on_tournament_over)
        self.client.server_found.connect(self._on_server_found)
        self.client.status.connect(self._on_status)
        self.client.walkover.connect(self._on_walkover)
        self.client.force_end.connect(self._on_force_end)
        self.client.time_sync.connect(lambda ms, p: self.battle.sync_time(ms, p))
        self.client.pause_broadcast.connect(self.battle.on_pause)
        self.client.resume_broadcast.connect(self.battle.on_resume)
        self.client.countdown_signal.connect(self._on_countdown)
        self.client.full_state.connect(self._on_full_state)
        self.client.error.connect(lambda m: self.login.set_status(f"错误: {m}"))
        self.client.manual_ip_requested.connect(
            lambda: self.login.show_manual())

        self.client.connection_lost.connect(self._on_connection_lost)
        self.client.reconnected.connect(self._on_reconnected)

    # ── 键盘事件（主窗口级别） ─────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        # 若当前在排名页，让排名页自己处理（已 accept，不会传到这里）
        if event.key() == Qt.Key.Key_F11:
            self._fullscreen = not self._fullscreen
            self.showFullScreen() if self._fullscreen else self.showNormal()
        elif event.key() == Qt.Key.Key_Escape:
            r = QMessageBox.question(
                self, "退出确认", "确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                self.client.stop()
                QApplication.quit()
        else:
            super().keyPressEvent(event)

    # ── 连接流程 ──────────────────────────────────────────────────
    def _on_connect(self, name, host, port):
        self.client.stop()
        self.client.set_server(host, port)
        self.client.start()

        def retry():
            if self.client._ws:
                self.client.auth(name)
            elif not host:
                QTimer.singleShot(500, retry)

        QTimer.singleShot(800 if host else 2500, retry)

    def _on_server_found(self, host, port):
        self.login.set_status(f"✨ 已找到服务器 {host}:{port}，连接中...")

    def _on_status(self, msg):
        self.login.set_status(msg)

    # ── 页面切换事件 ──────────────────────────────────────────────
    def _on_connected(self, data: dict):
        if "error" in data:
            self.login.join_timeout_timer.stop()
            self.login.btn.setEnabled(True)
            self.login.set_status(f"加入失败: {data['error']}")
            return
        self.login.join_timeout_timer.stop()
        self.login.btn.setEnabled(True)
        self.lobby.update_players(data.get("s", []))
        self._switch(PAGE_LOBBY)

    def _on_match_begin(self, info):
        self.battle.start_race(info)
        self._switch(PAGE_BATTLE)

    def _on_round_end(self, info):
        my_name = self.client._reconnect_name
        winner = info.get('w', '')
        is_winner = winner == my_name
        self.battle.show_round_end(my_name, eliminated=not is_winner)

    def _on_countdown(self, seconds):
        self._switch(PAGE_BATTLE)
        # 切页后强制刷新布局，确保旧遮罩被覆盖
        self.battle.repaint()
        self.battle.show_countdown(seconds)

    def _on_full_state(self, state):
        """断线重连恢复"""
        self.battle.start_race(state)
        self._switch(PAGE_BATTLE)
        self.battle.sync_time(state.get("r", 60000), state.get("u", False))
        if state.get("u"):
            self.battle.on_pause(state.get("r", 60000))

    def _on_walkover(self):
        self._switch(PAGE_BATTLE)
        self.battle.show_walkover(player_name=self.client._reconnect_name)

    def _on_force_end(self, reason):
        self._switch(PAGE_BATTLE)
        self.battle.show_force_end(reason, on_return=self._on_back_to_lobby)

    def _on_tournament_over(self, ranking):
        """比赛结束 → 填充排名数据 → 切换到排名页"""
        if not ranking:
            return
        self.result.show_ranking(ranking, title="🏆  最终排名  🏆")
        self._switch(PAGE_RESULT)

    # ── 返回大厅 ──────────────────────────────────────────────────
    def _on_back_to_lobby(self):
        """排名页"返回大厅"回调 — 切换到大厅页"""
        self._switch(PAGE_LOBBY)

    # ── 进度 / 按键上报 ───────────────────────────────────────────
    def _on_progress(self, c, e, t):
        self.client.send_progress(c, e, t)

    # ── 断连处理 ──────────────────────────────────────────────────
    def _on_connection_lost(self, reason):
        """断开连接时显示遮罩层"""
        if not self.disconnect_overlay:
            self.disconnect_overlay = MessageOverlay(self)
            self.disconnect_overlay.add_button("🔄 重连", self._on_reconnect, "#2980B9")

        self.disconnect_overlay.set_message(
            f"与服务器断开连接\n\n{reason}", color="#C0392B")
        self.disconnect_overlay.show()
        self.client.stop()

    def _on_reconnected(self):
        """重连成功，关闭遮罩层"""
        if self.disconnect_overlay:
            self.disconnect_overlay.hide_overlay()
        self.login.set_status("已重连")

    def _on_reconnect(self):
        """尝试重新连接"""
        self.disconnect_overlay.set_message("正在重新连接...", color="#F39C12")
        self.disconnect_overlay.clear_buttons()

        # 停掉旧的重连尝试，重新开始
        self.client.stop()
        if self.client.isRunning():
            self.client.wait(2000)
        self.client.set_server(self.client._host, self.client._port)
        self.client.start()

        def do_reconnect_auth():
            if self.client._ws:
                if self.client._pid:
                    self.client.send_reconnect()
                elif self.client._reconnect_name:
                    self.client.auth(self.client._reconnect_name)
            else:
                QTimer.singleShot(500, do_reconnect_auth)

        QTimer.singleShot(1000, do_reconnect_auth)
        QTimer.singleShot(4000, self._restore_reconnect_button)

    def _restore_reconnect_button(self):
        """恢复重连按钮"""
        if self.disconnect_overlay:
            self.disconnect_overlay.clear_buttons()
            self.disconnect_overlay.add_button("🔄 重连", self._on_reconnect, "#2980B9")


if __name__ == "__main__":
    sys.excepthook = global_exception_handler

    try:
        setup_logger("client", "client")
        logger = get_logger("client")
        logger.info("=" * 50)
        logger.info("打字对战客户端启动")
        logger.info("=" * 50)
    except Exception as e:
        print(f"初始化日志失败: {e}")
        import traceback
        traceback.print_exc()

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str)
    parser.add_argument("--host", type=str)
    parser.add_argument("--port", type=int, default=8888)
    args, _ = parser.parse_known_args()

    try:
        app = QApplication(sys.argv)
        app.setStyleSheet(BASE_STYLE)
        w = MainWindow(auto_name=args.name, auto_host=args.host, auto_port=args.port)
        w.show()
        sys.exit(app.exec())
    except Exception as e:
        try:
            logger = get_logger("client")
            logger.critical("主程序异常退出", exc_info=True)
        except Exception:
            pass
        raise
