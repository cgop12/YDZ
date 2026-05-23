"""common 包 - 共享模块"""
from .logger import setup_logger, get_logger
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont

AVATAR_COLORS = [
    "#E74C3C", "#3498DB", "#2ECC71", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#34495E", "#16A085", "#C0392B",
    "#2980B9", "#27AE60", "#8E44AD", "#2C3E50", "#D35400", "#7F8C8D",
]

class AvatarWidget(QWidget):
    def __init__(self, name: str, size: int = 60, color: str = None, parent=None):
        super().__init__(parent)
        self._char = name[0] if name else ""
        self._size = size
        self._bg = color or (AVATAR_COLORS[abs(hash(name)) % len(AVATAR_COLORS)] if name else "#CCCCCC")
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(1, 1, self._size - 2, self._size - 2)
        p.setBrush(QBrush(QColor(self._bg)))
        p.setPen(QPen(QColor("#222222"), 2))
        p.drawPath(path)
        if self._char:
            fs = max(10, int(self._size * 0.45))
            p.setFont(QFont("Microsoft YaHei", fs, QFont.Weight.Bold))
            p.setPen(QColor("#FFFFFF"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._char)

    def set_name(self, name: str):
        self._char = name[0] if name else ""
        self._bg = (AVATAR_COLORS[abs(hash(name)) % len(AVATAR_COLORS)]
                    if name else "#CCCCCC")
        self.update()

__all__ = ['setup_logger', 'get_logger', 'AVATAR_COLORS', 'AvatarWidget']
