"""大厅页 — 网格卡片布局，5列显示 32 个选手位置

布局参考 ui_demo.py LobbyPage：
  - QGridLayout 5列
  - 每格：圆形头像(52px) + 名字标签，居中排列
  - 空位显示"等待中..."（灰色文字，无头像着色）
  - 可滚动，支持 32 人
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from common import AvatarWidget


class LobbyPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F5F6FA;")
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(0, 0, 0, 0)

        # 顶部标题
        self.header = QLabel("🏟  选手大厅  ·  已连接: 0/32")
        self.header.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(
            "color: #1A1A2E; padding: 10px 0; background: transparent;")
        root.addWidget(self.header)

        # 可滚动网格区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(16)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        scroll.setWidget(self._grid_container)
        root.addWidget(scroll, stretch=1)

        # 房间信息栏
        self.info = QLabel("等待管理员开始比赛...")
        self.info.setFont(QFont("Microsoft YaHei", 11))
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info.setStyleSheet(
            "color: #333333; padding: 8px 16px; background: #E8EAF0; "
            "border: 1px solid #D0D3D9; border-radius: 6px;")
        root.addWidget(self.info)

        # 提示栏
        self.tip = QLabel("等待管理员开始比赛...")
        self.tip.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        self.tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tip.setStyleSheet("color: #D35400; background: transparent;")
        root.addWidget(self.tip)

        hint = QLabel("F11 全屏  |  Esc 退出")
        hint.setFont(QFont("Microsoft YaHei", 9))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #999999; background: transparent;")
        root.addWidget(hint)

        # 内部状态
        self._slots_built = False
        self._slot_widgets: list[QWidget] = []
        self._slot_avatars: list[AvatarWidget] = []
        self._slot_labels: list[QLabel] = []
        self._prev_players: dict = {}

        self._build_slots([])

    # ── 构建 32 个插槽 ────────────────────────────────────────────
    def _build_slots(self, players: list):
        """一次性构建全部 32 个槽位（参考 ui_demo.py LobbyPage 构建逻辑）"""
        cols = 5
        for i in range(32):
            r, c = i // cols, i % cols
            name = players[i]["name"] if i < len(players) else ""

            aw = AvatarWidget(name, 52)
            lbl = QLabel(name if name else "等待中...")
            lbl.setFont(QFont("Microsoft YaHei", 9))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "color: #1A1A2E; background: transparent;"
                if name else "color: #AAAAAA; background: transparent;"
            )

            box = QVBoxLayout()
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setSpacing(6)
            box.addWidget(aw)
            box.addWidget(lbl)

            cw = QWidget()
            cw.setLayout(box)
            cw.setStyleSheet("background: transparent;")

            # 空位默认隐藏
            if not name:
                cw.setVisible(False)

            self._grid.addWidget(cw, r, c)
            self._slot_widgets.append(cw)
            self._slot_avatars.append(aw)
            self._slot_labels.append(lbl)

        self._slots_built = True

    # ── 更新选手列表 ──────────────────────────────────────────────
    def update_players(self, players: list):
        """接收服务端 player_list，差量更新槽位"""
        self.header.setText(f"🏟  选手大厅  ·  已连接: {len(players)}/32")

        if not self._slots_built:
            self._build_slots(players)
            self._prev_players = {
                i: players[i] if i < len(players) else None
                for i in range(32)
            }
            return

        current = {
            i: players[i] if i < len(players) else None
            for i in range(32)
        }

        for i in range(32):
            prev = self._prev_players.get(i)
            curr = current[i]

            if prev is None and curr is None:
                self._slot_widgets[i].setVisible(False)
                continue

            if curr is None:
                # 玩家离开
                self._slot_widgets[i].setVisible(False)
            else:
                # 新玩家或更新
                name = curr.get("name", "")
                prev_name = prev.get("name", "") if prev else ""
                if name != prev_name:
                    self._slot_avatars[i].set_name(name)
                    self._slot_labels[i].setText(name if name else "等待中...")
                    self._slot_labels[i].setStyleSheet(
                        "color: #1A1A2E; background: transparent;"
                        if name else "color: #AAAAAA; background: transparent;"
                    )
                self._slot_widgets[i].setVisible(True)

        self._prev_players = current

    def set_status(self, text: str):
        self.tip.setText(text)
