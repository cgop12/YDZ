"""拼音逐字输入引擎 — 从 DZ 项目移植，改为错误也前进"""

class PinyinEngine:
    """拼音逐字母输入引擎。

    将拼音文本（如 "wo shi xue sheng"）拆成字母序列，
    空格自动跳过不计数，每按一个字母比较下一个目标字母。
    与 DZ 原版不同：按错时**仍然前进**（记录错误），光标移到下一个。
    """

    def __init__(self, pinyin_text: str):
        self._raw = pinyin_text
        self._chars = [c for c in pinyin_text if c != ' ']
        self._idx_map = []  # maps typing_index -> raw_source index
        i = 0
        for ch in pinyin_text:
            if ch != ' ':
                self._idx_map.append(i)
            i += 1

        self.total = len(self._chars)
        self.position = 0
        self.errors = 0
        self._state = [''] * self.total  # '' | 'correct' | 'wrong'
        self._finished = False

    def process_char(self, ch: str):
        """处理单个输入字符，返回 (accepted, finished)。"""
        if self._finished:
            return False, True

        if ch in ('\b', '\x08'):
            if self.position > 0:
                self.position -= 1
                self._state[self.position] = ''
            return True, False

        if ch < ' ' or ch > '~':
            return False, False

        ch = ch.lower()
        expected = self._chars[self.position]

        if ch == expected:
            self._state[self.position] = 'correct'
            self.position += 1
        else:
            self._state[self.position] = 'wrong'
            self.errors += 1
            self.position += 1

        if self.position >= self.total:
            self._finished = True
        return True, self._finished

    def get_display_info(self):
        """返回 [{char, state}] 供 UI 逐字渲染。"""
        out = []
        for i, ch in enumerate(self._raw):
            if ch == ' ':
                out.append({'char': ch, 'state': 'space'})
                continue
            try:
                ti = self._idx_map.index(i)
            except ValueError:
                out.append({'char': ch, 'state': 'pending'})
                continue
            if ti < self.position:
                state = 'correct' if self._state[ti] == 'correct' else 'error'
                out.append({'char': ch, 'state': state})
            elif ti == self.position:
                out.append({'char': ch, 'state': 'current'})
            else:
                out.append({'char': ch, 'state': 'pending'})
        return out

    def get_progress(self):
        return self.position, self.total

    @property
    def is_finished(self):
        return self._finished
