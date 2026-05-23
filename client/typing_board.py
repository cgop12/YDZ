"""
打字面板 — 继承自 D:\\ccc 的 TypingBoard
QPainter 卡片排版 + 原生 IME + 抖动反馈 + 自动滚动
"""

import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QFontMetrics, QPen, QInputMethodEvent

FONT_SIZE = 28
MARGIN = 20
CARD_PADDING_X = 15
CARD_PADDING_Y = 12
CARD_SPACING = 10
SHAKE_AMPLITUDE = 3
PUNCTUATIONS = set("，。！？；：“”‘’（）《》〈〉【】『』、·…—_-.!?;:\"'()[]{}<> \t\n\r")

# 标点智能映射：中英文标点互相视为相等
PUNCTUATION_MAP = {
    # 英文 → 中文
    ',': '，',
    '.': '。',
    '?': '？',
    '!': '！',
    ';': '；',
    ':': '：',
    '(': '（',
    ')': '）',
    '[': '【',
    ']': '】',
    # '': '“',  '': '”', 中英文引号由 IME 处理
}


class TypingBoard(QWidget):
    """QPainter 绘制的打字面板，集成 IME 输入法"""

    char_typed = pyqtSignal(str)       # 用户输了一个字符
    backspaced = pyqtSignal()           # 用户按了退格
    cursor_moved = pyqtSignal(QRect)    # 光标位置变化

    def __init__(self, parent=None):
        super().__init__(parent)
        # ── 文本数据 ──
        self.full_text = ""
        self._typed_chars: list[str] = []      # 用户实际输入的字符
        self._typed_correct: list[bool] = []   # 每个位置对/错
        self._pinyin_engine = None
        self._is_pinyin = False

        # ── IME 预编辑文本 ──
        self.preedit_text = ""

        # ── 字体 ──
        self._font = QFont("Microsoft YaHei", FONT_SIZE)
        self._fm = QFontMetrics(self._font)

        # ── 布局缓存 ──
        self.lines_info: list[dict] = []

        # ── 输入法支持 ──
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)

        # ── 抖动 ──
        self._shake_timer = QTimer(self)
        self._shake_timer.timeout.connect(self.update)
        self._shake_timer.start(50)

    # ════════════ 外部接口 ════════════

    def start_game(self, text: str, pinyin_engine=None):
        """设置本轮文本并开始"""
        self._is_pinyin = pinyin_engine is not None
        self._pinyin_engine = pinyin_engine

        # 清理
        self.full_text = text
        self._typed_chars.clear()
        self._typed_correct.clear()
        self.preedit_text = ""
        self.lines_info.clear()
        self._calculate_layout()
        self.setFocus()
        self.update()

    def reset(self):
        """重置状态"""
        self.full_text = ""
        self._typed_chars.clear()
        self._typed_correct.clear()
        self.preedit_text = ""
        self.lines_info.clear()
        self.update()

    # ════════════ 布局 ════════════

    def _calculate_layout(self):
        self.lines_info.clear()
        w = self.width()
        if w < 100 or not self.full_text:
            self.setMinimumHeight(200)
            return

        fm = self._fm
        line_height = fm.height() * 2 + 8 + CARD_PADDING_Y * 2

        current_x = MARGIN + CARD_PADDING_X
        current_y = MARGIN + CARD_PADDING_Y
        line_chars, start_idx = [], 0

        for i, char in enumerate(self.full_text):
            cw = fm.horizontalAdvance(char)
            if current_x + cw > w - MARGIN - CARD_PADDING_X and line_chars:
                rect = QRect(MARGIN, int(current_y - CARD_PADDING_Y),
                             w - MARGIN * 2, int(line_height))
                self.lines_info.append({
                    "start_idx": start_idx, "chars": line_chars,
                    "rect": rect
                })
                current_x = MARGIN + CARD_PADDING_X
                current_y += line_height + CARD_SPACING
                line_chars, start_idx = [], i
            line_chars.append((current_x, current_y, cw, char))
            current_x += cw

        if line_chars:
            rect = QRect(MARGIN, int(current_y - CARD_PADDING_Y),
                         w - MARGIN * 2, int(line_height))
            self.lines_info.append({
                "start_idx": start_idx, "chars": line_chars,
                "rect": rect
            })

        self.setMinimumHeight(int(current_y + line_height + MARGIN))

    def resizeEvent(self, event):
        self._calculate_layout()
        super().resizeEvent(event)

    # ════════════ 绘制 ════════════

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font)
        fm = self._fm
        t = _now_ms() / 100.0

        for line in self.lines_info:
            # 卡片背景
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#d0d0d0"), 1))
            painter.drawRoundedRect(line["rect"], 8, 8)

            for i, (x, y, cw, char_orig) in enumerate(line["chars"]):
                gidx = line["start_idx"] + i
                is_error = (gidx < len(self._typed_correct)
                            and not self._typed_correct[gidx])

                offset_y = (math.sin(t * 2) * SHAKE_AMPLITUDE) if is_error else 0

                # 原文（已完成→灰色，未完成→深灰）
                if gidx < len(self._typed_chars):
                    painter.setPen(QColor(180, 180, 180))
                else:
                    painter.setPen(QColor(100, 100, 100))
                painter.drawText(int(x), int(y + fm.ascent()), char_orig)

                # 输入层（已完成）
                if gidx < len(self._typed_chars):
                    if is_error:
                        painter.setPen(QColor(220, 40, 40))
                    else:
                        painter.setPen(QColor(40, 160, 40))
                    painter.drawText(
                        int(x), int(y + fm.height() + 4 + fm.ascent() + offset_y),
                        self._typed_chars[gidx])

                # 当前光标位
                if gidx == len(self._typed_chars):
                    pre_w = fm.horizontalAdvance(self.preedit_text)

                    # 预输入文本（蓝色，IME 候选拼音）
                    if self.preedit_text:
                        painter.setPen(QColor(50, 50, 200))
                        painter.drawText(
                            int(x), int(y + fm.height() + 4 + fm.ascent()),
                            self.preedit_text)

                    # 光标
                    painter.setPen(QPen(QColor(0, 0, 0), 2))
                    painter.drawLine(
                        int(x + pre_w), int(y + fm.height() + 4),
                        int(x + pre_w), int(y + fm.height() * 2 + 4))

    # ════════════ IME ─ 输入法 ════════════

    def inputMethodQuery(self, query):
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            target_idx = len(self._typed_chars)
            for line in self.lines_info:
                if line["start_idx"] <= target_idx < line["start_idx"] + len(line["chars"]):
                    x, y, _, _ = line["chars"][target_idx - line["start_idx"]]
                    pre_w = self._fm.horizontalAdvance(self.preedit_text)
                    return QRect(
                        int(x + pre_w), int(y + self._fm.height() + 4),
                        2, self._fm.height())
        return super().inputMethodQuery(query)

    def inputMethodEvent(self, event: QInputMethodEvent):
        self.preedit_text = event.preeditString()
        commit = event.commitString()
        if commit:
            for ch in commit:
                self._accept_char(ch)
        self.update()
        self.cursor_moved.emit(self._current_line_rect())
        # 防止 QLineEdit 默认行为
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Escape,):
            event.ignore()
            return

        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Backspace:
            if self._typed_chars:
                self._typed_chars.pop()
                self._typed_correct.pop()
                self.backspaced.emit()
                self.preedit_text = ""
            self.update()
            self.cursor_moved.emit(self._current_line_rect())
            event.accept()
            return

        ch = event.text()
        if not ch or ch == "\x7f":
            event.ignore()
            return

        # 普通字符 → 检查是否有 IME 正在拼写
        # 如果有预编辑文本，IME 会处理，我们不拦截
        if self.preedit_text:
            event.ignore()
            return

        self._accept_char(ch)
        self.update()
        self.cursor_moved.emit(self._current_line_rect())
        event.accept()

    # ════════════ 标点智能映射 ════════════

    @staticmethod
    def _normalize_punctuation(ch: str) -> str:
        """中英文标点统一到中文形式"""
        return PUNCTUATION_MAP.get(ch, ch)

    def _punctuation_matches(self, typed: str, expected: str) -> bool:
        """标点宽松匹配：中英文混输视为正确"""
        if typed == expected:
            return True
        return self._normalize_punctuation(typed) == self._normalize_punctuation(expected)

    # ════════════ 内部 ─ 接受字符 ════════════

    def _accept_char(self, ch: str):
        if len(self._typed_chars) >= len(self.full_text):
            return
        expected = self.full_text[len(self._typed_chars)]
        # 标点智能归一化 — 仅通过映射表匹配，不允许任意标点跨字符
        if expected in PUNCTUATIONS:
            if self._punctuation_matches(ch, expected):
                ch = expected
        self._typed_chars.append(ch)
        correct = ch == expected
        self._typed_correct.append(correct)
        self.char_typed.emit(ch)

    # ════════════ 辅助 ════════════

    def _current_line_rect(self) -> QRect:
        target = len(self._typed_chars)
        for line in self.lines_info:
            if line["start_idx"] <= target < line["start_idx"] + len(line["chars"]):
                return line["rect"]
        return QRect(0, 0, 0, 0)

    @property
    def typed_index(self) -> int:
        return len(self._typed_chars)

    @property
    def typed_count(self) -> int:
        return len(self._typed_chars)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self._typed_correct if not c)


def _now_ms() -> int:
    from PyQt6.QtCore import QTime
    return QTime.currentTime().msecsSinceStartOfDay()
