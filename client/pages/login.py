"""登录页 — 自动发现为主，手动输入为辅"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class LoginPage(QWidget):
    def __init__(self, on_connect):
        super().__init__()
        self.on_connect = on_connect
        self.setStyleSheet("background-color: #F5F6FA;")

        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(16)

        t = QLabel("🖮  局域网打字对战")
        t.setFont(QFont("Microsoft YaHei", 28, QFont.Weight.Bold))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("color: #1A1A2E; background: transparent;")
        l.addLayout(self._c(t))

        s = QLabel("输入你的名字，点击加入比赛")
        s.setFont(QFont("Microsoft YaHei", 12))
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet("color: #333; background: transparent;")
        l.addLayout(self._c(s))

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("输入你的名字")
        self.name_input.setFont(QFont("Microsoft YaHei", 14))
        self.name_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_input.setFixedWidth(300)
        self.name_input.setStyleSheet(
            "QLineEdit { padding:10px; border:2px solid #AAA; border-radius:8px; background:#FFF; color:#222; }"
            "QLineEdit:focus { border-color:#2980B9; }")
        self.name_input.returnPressed.connect(self._go)
        l.addLayout(self._c(self.name_input))

        # 手动连接（默认隐藏，自动发现失败后展开）
        self.manual_toggle = QPushButton("▼ 手动输入IP")
        self.manual_toggle.setFont(QFont("Microsoft YaHei", 9))
        self.manual_toggle.setFixedWidth(200)
        self.manual_toggle.setStyleSheet(
            "QPushButton { color:#2980B9; background:transparent; border:none; }"
            "QPushButton:hover { color:#1F6DA0; }")
        self.manual_toggle.clicked.connect(self._toggle_manual)
        l.addLayout(self._c(self.manual_toggle))

        self.manual_frame = QFrame()
        self.manual_frame.setStyleSheet("background: transparent;")
        self.manual_frame.hide()
        ml = QVBoxLayout(self.manual_frame)
        ml.setSpacing(6)

        ip_label = QLabel("服务器 IP 地址")
        ip_label.setFont(QFont("Microsoft YaHei", 10))
        ip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip_label.setStyleSheet("color: #C0392B; background: transparent; font-weight: bold;")
        ml.addWidget(ip_label)

        ip_row = QHBoxLayout()
        ip_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.ip_input = QLineEdit("192.168.1.100")
        self.ip_input.setFixedWidth(160)
        self.ip_input.setStyleSheet("padding:6px; border:1px solid #CCC; border-radius:4px;")
        ip_row.addWidget(self.ip_input)

        col_label = QLabel(":")
        col_label.setStyleSheet("color: #333; background: transparent;")
        ip_row.addWidget(col_label)

        self.port_input = QLineEdit("8888")
        self.port_input.setFixedWidth(70)
        self.port_input.setStyleSheet("padding:6px; border:1px solid #CCC; border-radius:4px;")
        ip_row.addWidget(self.port_input)

        ml.addLayout(ip_row)
        l.addLayout(self._c(self.manual_frame))

        self.btn = QPushButton("加入比赛")
        self.btn.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        self.btn.setFixedWidth(240)
        self.btn.setStyleSheet(
            "QPushButton { padding:12px 40px; background:#2980B9; color:white; border:none; border-radius:8px; }"
            "QPushButton:hover { background:#1F6DA0; }"
            "QPushButton:disabled { background:#BDC3C7; }")
        self.btn.clicked.connect(self._go)
        l.addLayout(self._c(self.btn))

        # 底部提示
        self.status = QLabel("输入名字，点击自动搜索服务器")
        self.status.setFont(QFont("Microsoft YaHei", 10))
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: #555; background: transparent;")
        l.addLayout(self._c(self.status))

        # 加入按钮超时定时器
        self.join_timeout_timer = QTimer()
        self.join_timeout_timer.setSingleShot(True)
        self.join_timeout_timer.timeout.connect(self._on_join_timeout)

        hint = QLabel("F11 全屏  |  Esc 退出")
        hint.setFont(QFont("Microsoft YaHei", 9))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #999; background: transparent; margin-top: 20px;")
        l.addLayout(self._c(hint))

    def _c(self, w):
        c = QHBoxLayout()
        c.addStretch()
        c.addWidget(w)
        c.addStretch()
        return c

    def _toggle_manual(self):
        self.manual_frame.setVisible(not self.manual_frame.isVisible())
        self.manual_toggle.setText(
            "▲ 收起" if self.manual_frame.isVisible() else "▼ 手动输入IP")

    def _go(self):
        name = self.name_input.text().strip()
        if not name:
            self.status.setText("⚠ 请输入名字")
            self.status.setStyleSheet("color: #C0392B; background: transparent; font-weight: bold;")
            return
        if len(name) > 16:
            self.status.setText("⚠ 名字长度需在1-16字符之间")
            self.status.setStyleSheet("color: #C0392B; background: transparent; font-weight: bold;")
            return

        self.btn.setEnabled(False)
        self.join_timeout_timer.start(3000)

        if self.manual_frame.isVisible():
            try:
                host = self.ip_input.text().strip()
                port = int(self.port_input.text().strip())
                self.status.setText(f"连接 {host}:{port}...")
                self.status.setStyleSheet("color: #555; background: transparent;")
                self.on_connect(name, host, port)
            except ValueError:
                self.status.setText("⚠ 端口格式错误")
                self.status.setStyleSheet("color: #C0392B; background: transparent; font-weight: bold;")
                self.join_timeout_timer.stop()
                self.btn.setEnabled(True)
        else:
            # 自动发现模式
            self.status.setText("🔍 搜索服务器中...")
            self.status.setStyleSheet("color: #555; background: transparent;")
            self.on_connect(name, None, None)

    def show_manual(self):
        """自动发现失败，展开手动输入"""
        self.manual_frame.show()
        self.manual_toggle.setText("▲ 收起")
        self.status.setText("⚠ 未发现服务器，请手动输入 IP")
        self.status.setStyleSheet("color: #C0392B; background: transparent; font-weight: bold;")
        self.join_timeout_timer.stop()
        self.btn.setEnabled(True)

    def set_status(self, text):
        self.join_timeout_timer.stop()
        self.status.setText(text)
        self.status.setStyleSheet("color: #555; background: transparent;")
        self.btn.setEnabled(True)

    def _on_join_timeout(self):
        self.btn.setEnabled(True)
        self.status.setText("⏳ 连接超时")
        self.status.setStyleSheet("color: #C0392B; background: transparent; font-weight: bold;")
