"""等候页 — 轮空/等待提示页"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class WaitingPage(QWidget):
    """轮空或两轮之间等待时的显示页面"""

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F0F2F5;")
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(20)

        self.icon = QLabel("🎉")
        self.icon.setFont(QFont("Segoe UI Emoji", 72))
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(self.icon)

        self.title = QLabel("本轮轮空")
        self.title.setFont(QFont("Microsoft YaHei", 36, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #27AE60; background: transparent;")
        l.addWidget(self.title)

        self.message = QLabel("自动晋级，等待下一轮比赛...")
        self.message.setFont(QFont("Microsoft YaHei", 20))
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setStyleSheet("color: #555; background: transparent;")
        l.addWidget(self.message)

        # 加载动画提示
        self.dots = QLabel(".")
        self.dots.setFont(QFont("Microsoft YaHei", 28))
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dots.setStyleSheet("color: #999; background: transparent;")
        l.addWidget(self.dots)

    def show_walkover(self):
        """显示轮空提示"""
        self.icon.setText("🎉")
        self.icon.setStyleSheet("color: #27AE60; background: transparent;")
        self.title.setText("本轮轮空")
        self.title.setStyleSheet("color: #27AE60; background: transparent;")
        self.message.setText("自动晋级，等待下一轮比赛...")

    def show_waiting(self, msg: str = "等待下一轮比赛..."):
        """显示等待信息"""
        self.icon.setText("⏳")
        self.icon.setStyleSheet("color: #F39C12; background: transparent;")
        self.title.setText("等待中")
        self.title.setStyleSheet("color: #F39C12; background: transparent;")
        self.message.setText(msg)
