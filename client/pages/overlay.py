"""
遮罩层组件 — 仅保留断连/暂停用的 MessageOverlay

实现策略：
  - 作为子 QWidget 覆盖在父窗口上层（而非独立顶层窗口）
  - paintEvent 绘制半透明深色背景
  - raise_() 置顶
  - 吞噬鼠标/键盘事件实现视觉阻塞
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPainter, QColor


class Overlay(QWidget):
    """
    全屏遮罩层（子 Widget 方案）

    使用：
      ov = MessageOverlay(parent_widget)
      ov.set_message("文字", color="#CC0000")
      ov.add_button("按钮", callback)
      ov.show()          # 自动铺满父窗口并置顶
      ov.hide_overlay()  # 隐藏
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self.setWindowFlags(Qt.WindowType.Widget)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 中央卡片容器
        self._center = QWidget()
        self._center.setObjectName("overlayCenter")
        self._center_layout = QVBoxLayout(self._center)
        self._center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._center_layout.setContentsMargins(30, 30, 30, 30)

        main_layout.addWidget(self._center, alignment=Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def paintEvent(self, event):
        """半透明深色背景"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        super().paintEvent(event)

    def set_content(self, widget):
        """替换中央卡片内容"""
        while self._center_layout.count():
            child = self._center_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._center_layout.addWidget(widget)

    def _fit_to_parent(self):
        if self._parent:
            self.setGeometry(0, 0, self._parent.width(), self._parent.height())

    def show(self):
        self._fit_to_parent()
        super().show()
        self.raise_()

    def hide_overlay(self):
        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_to_parent()

    def mousePressEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            super().keyPressEvent(event)
        else:
            event.accept()


class MessageOverlay(Overlay):
    """
    消息遮罩层 — 显示大号文字 + 可选操作按钮

    用途：
      - 断开连接提示（带"重连"按钮）
      - 比赛暂停提示（无按钮，等服务端恢复）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_card()

    def _init_card(self):
        self._card = QWidget()
        self._card.setObjectName("msgCard")
        self._card.setStyleSheet("""
            QWidget#msgCard {
                background-color: rgba(255, 255, 255, 245);
                border-radius: 20px;
            }
        """)
        self._card.setFixedWidth(520)
        self._card.setMinimumHeight(200)

        card_layout = QVBoxLayout(self._card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(28)
        card_layout.setContentsMargins(40, 40, 40, 40)

        # 消息文字
        self._msg_lbl = QLabel("")
        self._msg_lbl.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        self._msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setStyleSheet(
            "color: #1A1A2E; background: transparent; padding: 10px;")
        card_layout.addWidget(self._msg_lbl)

        # 按钮行
        self._btn_row = QHBoxLayout()
        self._btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._btn_row.setSpacing(16)
        card_layout.addLayout(self._btn_row)

        self.set_content(self._card)

    def set_message(self, text: str, color: str = "#1A1A2E"):
        self._msg_lbl.setText(text)
        self._msg_lbl.setStyleSheet(
            f"color: {color}; background: transparent; padding: 10px;")

    def add_button(self, text: str, callback, bg_color: str = "#2980B9"):
        btn = QPushButton(text)
        btn.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        btn.setFixedSize(170, 52)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        darker = self._darken(bg_color)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg_color};
                color: white;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: {darker}; }}
            QPushButton:pressed {{ background: {self._darken(darker)}; }}
        """)
        btn.clicked.connect(callback)
        self._btn_row.addWidget(btn)

    def clear_buttons(self):
        while self._btn_row.count():
            child = self._btn_row.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.82) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02X}{g:02X}{b:02X}"


# 向后兼容占位（如有其他模块导入 RankingOverlay）
RankingOverlay = None
