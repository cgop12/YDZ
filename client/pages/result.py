"""结算排名页 — 独立 QWidget，在 QStackedWidget 内切换显示

布局（参考 ui_demo.py ResultPage）：
  - 顶部标题
  - 前三名 Podium：2名(左) / 1名(中大) / 3名(右)  居中水平排列
  - 分隔线
  - 4名及以后：可滚动垂直列表，每条居中、带头像
  - 底部"返回大厅"按钮（点击 或 按 Enter）

键盘：
  - Enter / Return → 触发返回大厅
  - 调用 event.accept() 阻止事件冒泡
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from common import AvatarWidget, AVATAR_COLORS


def _make_podium_item(name: str, rank_label: str, size: int,
                      avatar_color: str, rank_color: str) -> QWidget:
    """
    创建一个讲台项（头像 + 排名标签 + 名字）。
    复制自 ui_demo.py make_podium_item，加入 rank_label 在上方。
    """
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    vbox = QVBoxLayout(w)
    vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
    vbox.setSpacing(4)

    # 排名标签
    rl = QLabel(rank_label)
    rl.setFont(QFont("Microsoft YaHei", 13 if size < 100 else 16, QFont.Weight.Bold))
    rl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    rl.setStyleSheet(f"color: {rank_color}; background: transparent;")
    vbox.addWidget(rl)

    # 头像
    aw = AvatarWidget(name, size, avatar_color)
    vbox.addWidget(aw, alignment=Qt.AlignmentFlag.AlignCenter)

    # 名字
    nl = QLabel(name)
    nl.setFont(QFont("Microsoft YaHei", 11 if size < 100 else 14, QFont.Weight.Bold))
    nl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nl.setStyleSheet("color: #1A1A2E; background: transparent;")
    vbox.addWidget(nl)

    return w


class ResultPage(QWidget):
    """
    独立排名页面，通过 QStackedWidget 切换显示。

    公开接口：
      show_ranking(ranking: list)  — 填充排名数据并（由 main 切换到此页）
      on_back_to_lobby: callable   — 返回大厅的回调，由 main.py 注入
    """

    # 讲台配置：(尺寸, 头像色, 排名色, 排名文字)
    _PODIUM_CFG = [
        (90,  "#E67E22", "#D35400", "🥈 第2名"),   # 左：第2名
        (130, "#C0392B", "#C0392B", "🥇 第1名"),   # 中：第1名（最高）
        (70,  "#2980B9", "#2471A3", "🥉 第3名"),   # 右：第3名
    ]
    # 讲台显示顺序：ranking[1], ranking[0], ranking[2]
    _PODIUM_ORDER = [1, 0, 2]

    def __init__(self, on_back_to_lobby=None):
        super().__init__()
        self.on_back_to_lobby = on_back_to_lobby
        self.setStyleSheet("background-color: #F5F6FA;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build()

    # ── 构建固定骨架 ──────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(6)

        # 标题
        self._title = QLabel("🏆  最终排名  🏆")
        self._title.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            "color: #1A1A2E; padding: 10px 0 5px 0; background: transparent;")
        root.addWidget(self._title)

        # 前三名讲台区（HBoxLayout，居中）
        self._podium_row = QHBoxLayout()
        self._podium_row.setSpacing(25)
        self._podium_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addLayout(self._podium_row)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #BBBBBB; margin: 4px 0;")
        root.addWidget(sep)

        # 滚动列表（4名及以后）
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setSpacing(4)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._scroll.setWidget(self._list_widget)
        root.addWidget(self._scroll, stretch=1)

        # 底部按钮行
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(20)

        self._back_btn = QPushButton("🏠 返回大厅")
        self._back_btn.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        self._back_btn.setFixedWidth(160)
        self._back_btn.setFixedHeight(44)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setStyleSheet("""
            QPushButton {
                padding: 10px;
                background: #2980B9;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background: #1F6DA0; }
            QPushButton:pressed { background: #1A5A80; }
        """)
        self._back_btn.clicked.connect(self._on_back)
        btn_row.addWidget(self._back_btn)

        root.addLayout(btn_row)

        hint = QLabel("按 Enter 返回大厅")
        hint.setFont(QFont("Microsoft YaHei", 9))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #999999; background: transparent;")
        root.addWidget(hint)

    # ── 填充排名数据 ──────────────────────────────────────────────
    def show_ranking(self, ranking: list, title: str = "🏆  最终排名  🏆"):
        """
        用排名数据填充页面。
        ranking: [{"name": "玩家名", "score": 分数}, ...] 按名次顺序（index 0 = 第1名）
        """
        self._title.setText(title)

        # ── 清除旧讲台 ──
        while self._podium_row.count():
            item = self._podium_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # ── 填充讲台（最多 3 人） ──
        if len(ranking) >= 1:
            for slot_idx, rank_idx in enumerate(self._PODIUM_ORDER):
                if rank_idx >= len(ranking):
                    continue
                player = ranking[rank_idx]
                name = player.get("name", "?")
                size, acolor, rcolor, rlabel = self._PODIUM_CFG[slot_idx]
                item_w = _make_podium_item(name, rlabel, size, acolor, rcolor)
                self._podium_row.addWidget(item_w)

        # ── 清除旧列表 ──
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # ── 填充 4 名及以后 ──
        remaining = ranking[3:]
        for i, player in enumerate(remaining):
            rank = i + 4
            name = player.get("name", "?")
            score = player.get("score", 0)
            color = AVATAR_COLORS[(rank - 1) % len(AVATAR_COLORS)]

            item_frame = QFrame()
            item_frame.setStyleSheet(
                "QFrame { background: #FFFFFF; border: 1px solid #D0D3D9; "
                "border-radius: 4px; }")
            item_frame.setFixedWidth(420)
            item_frame.setFixedHeight(50)

            row = QHBoxLayout(item_frame)
            row.setContentsMargins(0, 4, 12, 4)
            row.setSpacing(0)

            row.addStretch()

            rank_lbl = QLabel(f"第{rank}名")
            rank_lbl.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            rank_lbl.setFixedWidth(52)
            rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_lbl.setStyleSheet(
                "color: #555555; background: transparent; border: none; padding: 0;")
            row.addWidget(rank_lbl)

            row.addSpacing(10)
            aw = AvatarWidget(name, 36, color)
            row.addWidget(aw)

            row.addSpacing(8)
            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Microsoft YaHei", 11))
            name_lbl.setMinimumWidth(80)
            name_lbl.setStyleSheet(
                "color: #1A1A2E; background: transparent; border: none; padding: 0;")
            row.addWidget(name_lbl)

            row.addSpacing(20)
            score_lbl = QLabel(f"{score} 分")
            score_lbl.setFont(QFont("Microsoft YaHei", 10))
            score_lbl.setStyleSheet(
                "color: #666666; background: transparent; border: none; padding: 0;")
            row.addWidget(score_lbl)

            row.addStretch()

            self._list_layout.addWidget(
                item_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # 确保获取焦点，使 keyPressEvent 生效
        self.setFocus()

    # ── 键盘事件 ──────────────────────────────────────────────────
    def keyPressEvent(self, event):
        """Enter 键触发返回大厅；阻止事件冒泡到主窗口"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()      # 阻止冒泡
            self._on_back()
            return
        # F11 传给父级处理全屏，其他键一律吞掉（避免误触对战输入框等）
        if event.key() == Qt.Key.Key_F11:
            super().keyPressEvent(event)
        else:
            event.accept()

    # ── 返回大厅 ──────────────────────────────────────────────────
    def _on_back(self):
        """触发返回大厅回调"""
        if self.on_back_to_lobby:
            self.on_back_to_lobby()
