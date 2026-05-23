"""
对战页 — QPainter 卡片式打字面板 + 原生 IME
集成自 D:\\ccc\\11.py 的 TypingBoard
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QFont, QResizeEvent

try:
    from overlay import MessageOverlay
except ImportError:
    from pages.overlay import MessageOverlay

from typing_board import TypingBoard
from common.pinyin_compare import PinyinEngine


class BattlePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F0F0F0;")

        # ── 比赛状态 ──
        self.match_text = ""
        self.total_duration = 60
        self.remaining_ms = 60000
        self._paused = False
        self.is_racing = False
        self._last_send_progress = 0.0

        self._pinyin_engine = None
        self._is_pinyin = False

        # ── 外部回调 ──
        self.on_progress = None

        # ── 是否已被淘汰 ──
        self._eliminated = False

        # ── 服务器同步缓存 ──
        self._server_ack_pending = {}

        # ── 暂停遮罩 ──
        self.pause_overlay = None

        # ── 底部统计（倒计时/WPM/进度/正确率） ──
        self._stats = {"comp": 0, "errs": 0, "pct": 0, "acc": 100.0, "speed": 0}

        # ── 主定时器 ──
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

        self._build()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if hasattr(self, '_countdown_overlay') and self._countdown_overlay:
            self._countdown_overlay.setGeometry(self.rect())
        if hasattr(self, '_countdown_bg') and self._countdown_bg:
            self._countdown_bg.setGeometry(self.rect())

    # ════════════ 构建 UI ════════════

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        # ── 标题栏 ──
        self.header = QLabel("等待比赛...")
        self.header.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(
            "color:#333; padding:8px; background:transparent;")
        root.addWidget(self.header)

        # ── 覆盖文字（兼容旧 main.py 的 overlay 调用） ──
        self.overlay = QLabel()
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setWordWrap(True)
        self.overlay.hide()
        self.overlay.setStyleSheet(
            "color:#27AE60; font-size:32px; background:transparent;")
        root.addWidget(self.overlay)

        # ── 打字面板（可滚动） ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{width:8px;}"
            "QScrollBar::handle:vertical{background:#bbb;border-radius:4px;}")

        self._board = TypingBoard()
        self._board.char_typed.connect(self._on_board_char)
        self._board.backspaced.connect(self._on_board_backspace)
        self._board.cursor_moved.connect(self._on_board_cursor_moved)
        self._scroll.setWidget(self._board)
        root.addWidget(self._scroll, stretch=1)

        # ── 底部统计栏 ──
        self._build_bottom_bar(root)

        # ── 强制结束遮罩 ──
        self._force_overlay = None
        self._force_callback = None
        self._force_remaining = 0
        self._force_count_timer = None

    def _build_bottom_bar(self, parent_layout):
        bar = QFrame()
        bar.setStyleSheet(
            "QFrame{background:#FFF;"
            "border:2px solid #C0C0C0;border-radius:20px;padding:10px 20px;}")
        layout = QHBoxLayout(bar)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.time_label = QLabel("⏱ 00:00")
        self.time_label.setFont(
            QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.time_label.setStyleSheet("color:#333;")
        layout.addWidget(self.time_label)

        self.speed_label = QLabel("⚡ 0字/分")
        self.speed_label.setFont(
            QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.speed_label.setStyleSheet("color:#333;")
        layout.addWidget(self.speed_label)

        self.progress_label = QLabel("📊 0%")
        self.progress_label.setFont(
            QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.progress_label.setStyleSheet("color:#333;")
        layout.addWidget(self.progress_label)

        self.accuracy_label = QLabel("🎯 100%")
        self.accuracy_label.setFont(
            QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.accuracy_label.setStyleSheet("color:#333;")
        layout.addWidget(self.accuracy_label)

        parent_layout.addWidget(bar)

    # ════════════ 打字面板回调 ════════════

    def _on_board_char(self, ch: str):
        """TypingBoard 收到一个字符"""
        if not self.is_racing or self._paused:
            return

        idx = self._board.typed_index - 1  # 刚填的字符索引
        if idx < 0:
            return

        if self._is_pinyin:
            # 拼音模式：交给 PinyinEngine
            if self._pinyin_engine:
                prev_err = self._pinyin_engine.errors
                accepted, _ = self._pinyin_engine.process_char(ch)
                if accepted:
                    new_err = self._pinyin_engine.errors > prev_err
                    if new_err:
                        self._shake()
                # PinyinEngine 有自己的 typed_index
        else:
            # 中文模式：直接比较
            pass  # TypingBoard 内部已经完成了比较

        self._update_stats()

    def _on_board_backspace(self):
        """TypingBoard 收到退格"""
        if self._is_pinyin and self._pinyin_engine:
            self._pinyin_engine.backspace()

    def _on_board_cursor_moved(self, rect: QRect):
        """光标移动 → 自动滚动"""
        # 确保整张卡片可见（卡片高度 ≈ 行高 × 2 + 内边距）
        self._scroll.ensureVisible(rect.x(), rect.y(), 20, 150)

    # ════════════ 外部接口 ════════════

    def start_race(self, info: dict):
        """开始比赛"""
        self.clear_overlays()
        chinese_text = info.get("x", "")
        self.total_duration = info.get("tt", 60)
        rn = info.get("n", "")
        opp = info.get("o", "???")
        pinyin_text = info.get("p", "")

        self._is_pinyin = bool(pinyin_text)
        self.match_text = chinese_text if not self._is_pinyin else pinyin_text

        if self._is_pinyin:
            self._pinyin_engine = PinyinEngine(pinyin_text)
        else:
            self._pinyin_engine = None

        self.is_racing = True
        self.remaining_ms = self.total_duration * 1000
        self._paused = False
        self._last_send_progress = 0.0
        self._stats = {"comp": 0, "errs": 0, "pct": 0, "acc": 100.0, "speed": 0}

        # 清除上一场残留（获胜信息、遮罩、轮空等）
        self.overlay.hide()
        if hasattr(self, '_walkover_overlay') and self._walkover_overlay:
            self._walkover_overlay.hide()
            self._walkover_overlay = None
        if hasattr(self, '_round_end_overlay') and self._round_end_overlay:
            self._round_end_overlay.hide()
            self._round_end_overlay = None
        self.header.setStyleSheet(
            "color:#333; padding:8px; background:transparent;")
        mode_tag = "🔤 " if self._is_pinyin else ""
        self.header.setText(f"{mode_tag}{rn} · vs {opp}")

        # 重置统计显示
        self.time_label.setText("⏱ 01:00")
        self.speed_label.setText("⚡ 0字/分")
        self.progress_label.setText("📊 0%")
        self.accuracy_label.setText("🎯 100%")

        self.clear_overlays()
        self._eliminated = False
        # 恢复 TypingBoard 焦点（可能被 show_round_end 设为了 NoFocus）
        self._board.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._board.start_game(self.match_text, self._pinyin_engine)

        # 启动倒计时
        self._timer.start(100)
        self._board.setFocus()

    def stop_race(self):
        """停止比赛"""
        self.is_racing = False
        self._timer.stop()

    def sync_time(self, remaining_ms: int, paused: bool):
        self.remaining_ms = remaining_ms
        self._paused = paused
        secs = max(0, int(remaining_ms / 1000))
        self.time_label.setText(f"⏱ {secs//60:02d}:{secs%60:02d}")

    def on_pause(self, remaining_ms: int):
        self.is_racing = False
        self.remaining_ms = remaining_ms
        if not self.pause_overlay:
            self.pause_overlay = MessageOverlay(self)
        self.pause_overlay.set_message("⏸ 比赛已暂停，请稍候", color="#F39C12")
        self.pause_overlay.show()

    def on_resume(self, remaining_ms: int):
        self.is_racing = True
        self.remaining_ms = remaining_ms
        self._board.setFocus()
        if self.pause_overlay:
            self.pause_overlay.close()

    def show_countdown(self, seconds: int):
        """全屏倒计时显示"""
        self.is_racing = False
        self.clear_overlays()

        if self._eliminated:
            # 已淘汰 → 全屏不透明遮罩，不显示倒计时
            self._eliminated_overlay = QLabel(self)
            self._eliminated_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._eliminated_overlay.setText(
                "❌ 你已被淘汰\n\n⏳ 等待本轮比赛结束...")
            self._eliminated_overlay.setStyleSheet(
                "background-color: #1a1a2e;"
                "color: #95a5a6; font-size: 28px; font-weight: bold;")
            self._eliminated_overlay.setGeometry(self.rect())
            self._eliminated_overlay.raise_()
            self._eliminated_overlay.show()
            return

        # 重置统计，滚动到顶部
        self._scroll.verticalScrollBar().setValue(0)
        self.time_label.setText(f"⏱ {seconds//60:02d}:{seconds%60:02d}")
        self.speed_label.setText("⚡ 0字/分")
        self.progress_label.setText("📊 0%")
        self.accuracy_label.setText("🎯 100%")

        # 全屏遮罩覆盖整个窗口
        self._countdown_overlay = QLabel(self)
        self._countdown_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_overlay.setStyleSheet(
            "color:#E74C3C;font-size:120px;font-weight:bold;")
        # 用 QFrame 子类做真正的全屏半透明遮罩
        self._countdown_bg = QFrame(self)
        self._countdown_bg.setStyleSheet(
            "background-color: rgba(0,0,0,200);")
        self._countdown_bg.setGeometry(self.rect())
        self._countdown_bg.show()

        self._countdown_overlay.setGeometry(self.rect())
        self._countdown_overlay.show()

        # 确保倒计时在最顶层（排除其他遮罩干扰）
        self._countdown_bg.raise_()
        self._countdown_overlay.raise_()

        self._countdown_value = seconds
        self._do_countdown()

    def _do_countdown(self):
        n = self._countdown_value
        if n <= 0:
            if hasattr(self, '_countdown_overlay') and self._countdown_overlay:
                self._countdown_overlay.hide()
                self._countdown_overlay.deleteLater()
                self._countdown_overlay = None
            if hasattr(self, '_countdown_bg') and self._countdown_bg:
                self._countdown_bg.hide()
                self._countdown_bg.deleteLater()
                self._countdown_bg = None
            return

        if self._countdown_overlay:
            self._countdown_overlay.setGeometry(self.rect())
            self._countdown_overlay.setText(str(n))
            self._countdown_overlay.raise_()

        self._countdown_value = n - 1
        QTimer.singleShot(1000, self._do_countdown)

    def show_force_end(self, reason: str, on_return=None):
        self.is_racing = False
        self._timer.stop()
        self.clear_overlays()
        self._eliminated = False

        self._force_callback = on_return
        self._force_remaining = 5
        self._force_reason = reason

        if not self._force_overlay:
            self._force_overlay = MessageOverlay(self)
        self._force_overlay.clear_buttons()
        self._force_overlay.add_button(
            "🏠 返回大厅", self._do_force_return, "#2980B9")
        self._force_overlay.show()
        self._update_force_msg()

        self._force_count_timer = QTimer()
        self._force_count_timer.timeout.connect(self._tick_force)
        self._force_count_timer.start(1000)

    def _update_force_msg(self):
        if self._force_overlay:
            self._force_overlay.set_message(
                f"⛔ {self._force_reason}\n\n"
                f"{self._force_remaining}秒后自动返回大厅",
                color="#C0392B")

    def _tick_force(self):
        self._force_remaining -= 1
        if self._force_remaining <= 0:
            self._do_force_return()
        else:
            self._update_force_msg()

    def _do_force_return(self):
        if self._force_count_timer:
            self._force_count_timer.stop()
        if self._force_overlay:
            self._force_overlay.hide_overlay()
        cb = self._force_callback
        self._force_overlay = None
        self._force_callback = None
        if cb:
            cb()

    def show_round_end(self, player_name: str, eliminated: bool = True):
        """全屏遮罩显示本场结果 — 三种状态各不同"""
        self._eliminated = eliminated
        self.is_racing = False
        self._timer.stop()
        self._board.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if eliminated:
            # 输家：你已被淘汰
            self._round_end_overlay = QLabel(self)
            self._round_end_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._round_end_overlay.setText(
                f"❌ {player_name}\n\n你已被淘汰")
            self._round_end_overlay.setStyleSheet(
                "background-color: #1a1a2e;"
                "color: #e74c3c; font-size: 36px; font-weight: bold;")
            self._round_end_overlay.setGeometry(self.rect())
            self._round_end_overlay.raise_()
            self._round_end_overlay.show()
        else:
            # 赢家：你已晋级
            self._round_end_overlay = QLabel(self)
            self._round_end_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._round_end_overlay.setText(
                f"🏆 {player_name}\n\n✅ 你已晋级，等待下轮比赛")
            self._round_end_overlay.setStyleSheet(
                "background-color: #1a1a2e;"
                "color: #27ae60; font-size: 36px; font-weight: bold;")
            self._round_end_overlay.setGeometry(self.rect())
            self._round_end_overlay.raise_()
            self._round_end_overlay.show()

    def show_walkover(self, player_name: str = ""):
        """轮空提示"""
        self.is_racing = False
        self._timer.stop()
        self._board.reset()
        self._scroll.verticalScrollBar().setValue(0)
        self.overlay.hide()
        self._round_end_overlay = QLabel(self)
        self._round_end_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_line = f"{player_name}\n\n" if player_name else ""
        self._round_end_overlay.setText(
            f"🔄 {name_line}本轮轮空\n\n自动晋级，等待下一轮比赛")
        self._round_end_overlay.setStyleSheet(
            "background-color: #1a1a2e;"
            "color: #2980b9; font-size: 36px; font-weight: bold;")
        self._round_end_overlay.setGeometry(self.rect())
        self._round_end_overlay.raise_()
        self._round_end_overlay.show()

    def show_winner(self, info: dict):
        self.is_racing = False
        self._timer.stop()
        winner = info.get('winner', '')
        self.header.setText(f"🎉 {winner} 获胜")
        self.header.setStyleSheet(
            "color:#27AE60; font-size:22px; padding:8px; background:transparent;")

    def show_overlay_text(self, text: str, color: str = "#27AE60"):
        """在打字面板上方显示覆盖文字（兼容旧版 main.py 调用）"""
        self.header.setText(text)
        self.header.setStyleSheet(
            f"color:{color}; font-size:22px; padding:8px; background:transparent;")

    # ════════════ 主循环 ════════════

    def _tick(self):
        if not self.is_racing:
            return

        # 倒计时
        self.remaining_ms = max(0, self.remaining_ms - 100)
        secs = int(self.remaining_ms / 1000)
        self.time_label.setText(f"⏱ {secs//60:02d}:{secs%60:02d}")

        # 更新统计（节流）
        self._update_stats()

        # 发送进度
        now_ms = _now_ms()
        if now_ms - self._last_send_progress >= 200 and self.on_progress:
            c = self._board.typed_count
            e = self._board.error_count
            elapsed = max(
                (self.total_duration * 1000 - self.remaining_ms) / 1000, 0.1)
            if c > 0 or e > 0:
                self.on_progress(c, e, elapsed)
            self._last_send_progress = now_ms

        # 时间到
        if self.remaining_ms <= 0:
            self.is_racing = False
            self._timer.stop()

    # ════════════ 统计更新 ════════════

    def _update_stats(self):
        comp = self._board.typed_count
        errs = self._board.error_count
        total = len(self.match_text) if self.match_text else 1

        pct = int(comp / max(total, 1) * 100)
        acc = round((comp - errs) / max(comp, 1) * 100, 1) if comp > 0 else 100.0
        elapsed_sec = max(
            (self.total_duration * 1000 - self.remaining_ms) / 1000, 0.1)
        speed = int(comp / max(elapsed_sec / 60, 0.1))

        self.progress_label.setText(f"📊 {pct}%")
        self.speed_label.setText(f"⚡ {speed}字/分")
        self.accuracy_label.setText(f"🎯 {acc}%")

        self._stats.update(comp=comp, errs=errs, pct=pct, acc=acc, speed=speed)

    # ════════════ 清理工具 ════════════

    def clear_overlays(self):
        """清除所有遮罩 — 从布局/父控件中移除以确保完全消失"""
        self.overlay.hide()
        for attr in ('_round_end_overlay', '_walkover_overlay',
                     '_eliminated_overlay', '_countdown_overlay',
                     '_countdown_bg', '_pause_overlay', '_force_overlay'):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.setParent(None)
                    obj.hide()
                    obj.deleteLater()
                except Exception:
                    pass
                setattr(self, attr, None)

    # ════════════ 错误抖动 ════════════

    def _shake(self):
        """触发抖动视觉效果（TypingBoard 内部已有抖动）"""
        pass  # TypingBoard 的 paintEvent 自带抖动

    # ════════════ 清理 ════════════

    def cleanup(self):
        self._timer.stop()
        if self._force_count_timer:
            self._force_count_timer.stop()
        self.clear_overlays()
        self._eliminated = False
        self.is_racing = False
        self._board.reset()


def _now_ms() -> int:
    from PyQt6.QtCore import QTime
    return QTime.currentTime().msecsSinceStartOfDay()
