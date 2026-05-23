"""统一模型层 — 客户端与服务端共享"""

import uuid
import random
from typing import Optional

# 标点统一为中文，避免客户端渲染重叠
_PUNCT_TO_CN = {
    ',': '，', '.': '。', '?': '？', '!': '！',
    ';': '；', ':': '：', '(': '（', ')': '）',
    '[': '【', ']': '】',
}

def _normalize_text(text: str) -> str:
    return ''.join(_PUNCT_TO_CN.get(c, c) for c in text)


WEIGHT_COMPLETION = 0.60
WEIGHT_ACCURACY = 0.30
WEIGHT_SPEED = 0.10
BASE_SPEED = 3.0
MAX_PLAYERS = 32

class Player:
    MAX_NAME_LENGTH = 16
    __slots__ = ('id', 'name', 'is_admin', 'ready')

    def __init__(self, pid: str, name: str):
        if not name or len(name) > Player.MAX_NAME_LENGTH:
            raise ValueError(f"名字长度需在1-{Player.MAX_NAME_LENGTH}字符之间")
        self.id = pid
        self.name = name
        self.is_admin = False

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


class MatchResult:
    __slots__ = ('completed', 'total', 'errors', 'elapsed')

    def __init__(self, completed: int, total: int, errors: int, elapsed: float):
        self.completed = completed
        self.total = total
        self.errors = errors
        self.elapsed = max(elapsed, 0.1)

    def score(self) -> float:
        cr = self.completed / self.total * 100
        acc = max(0, (self.completed - self.errors) / max(self.completed, 1)) * 100
        spd = min(100, (self.completed / self.elapsed) / BASE_SPEED * 100)
        return cr * WEIGHT_COMPLETION + acc * WEIGHT_ACCURACY + spd * WEIGHT_SPEED

    def to_dict(self) -> dict:
        return {
            "completed": self.completed,
            "total": self.total,
            "completion_rate": round(self.completed / self.total * 100, 1),
            "errors": self.errors,
            "accuracy": round(max(0, (self.completed - self.errors) / max(self.completed, 1)) * 100, 1),
            "elapsed": round(self.elapsed, 1),
            "score": round(self.score(), 1),
        }


class Match:
    __slots__ = ('p1', 'p2', 'text', 'pinyin_text', '_c1', '_e1', '_t1',
                 '_c2', '_e2', '_t2', 'winner', 'loser', 'finished')

    def __init__(self, p1: Player, p2: Player, text: str, pinyin_text: str = ""):
        if not p1 or not p2:
            raise ValueError("Match requires two valid players")
        if not text:
            raise ValueError("Match text cannot be empty")
        self.p1 = p1
        self.p2 = p2
        self.text = text
        self.pinyin_text = pinyin_text
        self._c1 = self._e1 = self._t1 = 0
        self._c2 = self._e2 = self._t2 = 0
        self.winner: Optional[Player] = None
        self.loser: Optional[Player] = None
        self.finished = False

    def update(self, pid: str, completed: int, errors: int, elapsed: float):
        if pid == self.p1.id:
            self._c1, self._e1, self._t1 = min(completed, len(self.text)), errors, elapsed
        else:
            self._c2, self._e2, self._t2 = min(completed, len(self.text)), errors, elapsed

    def get_result(self, pid: str) -> MatchResult:
        if pid == self.p1.id:
            return MatchResult(self._c1, len(self.text), self._e1, self._t1)
        return MatchResult(self._c2, len(self.text), self._e2, self._t2)

    def decide_winner(self):
        s1 = self.get_result(self.p1.id).score()
        s2 = self.get_result(self.p2.id).score()
        if s1 >= s2:
            self.winner, self.loser = self.p1, self.p2
        else:
            self.winner, self.loser = self.p2, self.p1
        self.finished = True


class Tournament:
    def __init__(self, text_manager=None):
        self.tm = text_manager
        self.players: dict[str, Player] = {}
        self.admin_id: Optional[str] = None
        self.alive: list[Player] = []
        self.matches: list[Match] = []
        self.current_round = 0
        self.total_rounds = 0
        self.ranking: list[dict] = []
        self.used_texts: list[str] = []
        self.bye_player: Optional[Player] = None

    def add_player(self, name: str) -> tuple[str, str]:
        if len(self.players) >= MAX_PLAYERS:
            return "", "房间已满"
        if not name or len(name) > Player.MAX_NAME_LENGTH:
            return "", f"名字长度需在1-{Player.MAX_NAME_LENGTH}字符之间"
        for p in self.players.values():
            if p.name == name:
                return "", "名字已被使用"
        pid = str(uuid.uuid4())[:8]
        p = Player(pid, name)
        if self.admin_id is None:
            p.is_admin = True
            self.admin_id = pid
        self.players[pid] = p
        return pid, ""

    def remove_player(self, pid: str):
        if pid in self.players:
            del self.players[pid]
        if pid == self.admin_id:
            for p in self.players.values():
                p.is_admin = True
                self.admin_id = p.id
                break

    def player_list(self) -> list[dict]:
        return [p.to_dict() for p in self.players.values()]

    def can_start(self) -> bool:
        return len(self.players) >= 2

    def init_tournament(self):
        self.alive = list(self.players.values())
        self.current_round = 0
        self.matches = []
        self.ranking = []
        self.used_texts = []
        n = len(self.alive)
        r = 0
        while n > 1:
            n = (n + 1) // 2
            r += 1
        self.total_rounds = r

    def create_round_matches(self, custom_texts: list[str] | None = None, custom_pinyin: list[str] | None = None):
        self.current_round += 1
        random.shuffle(self.alive)
        needed = (len(self.alive) + 1) // 2

        # 优先使用参数传入的文本，其次 _custom_texts，最后题库随机
        if custom_texts:
            texts = custom_texts
        elif hasattr(self, '_custom_texts') and self._custom_texts:
            texts = self._custom_texts
            self._custom_texts = []  # 用完后清空，下一轮走题库
        elif self.tm:
            texts = self.tm.pick_batch(needed, exclude=self.used_texts)
        else:
            texts = []

        matches = []
        for i in range(0, len(self.alive) - 1, 2):
            t = texts[i // 2] if i // 2 < len(texts) else (self.tm.pick_random() if self.tm else "")
            pt = custom_pinyin[i // 2] if custom_pinyin and i // 2 < len(custom_pinyin) else ""
            # 确保文本标点统一
            t = _normalize_text(t)
            matches.append(Match(self.alive[i], self.alive[i + 1], t, pt))
        self.bye_player = self.alive[-1] if len(self.alive) % 2 == 1 else None
        self.matches.extend(matches)
        return matches

    def finish_round(self, matches: list[Match]):
        winners = []
        for m in matches:
            if not m.finished:
                m.decide_winner()
            if m.winner:
                winners.append(m.winner)
            if m.loser:
                r = m.get_result(m.loser.id).to_dict()
                self.ranking.append({
                    "name": m.loser.name,
                    "score": r["score"],
                    "completion": r["completion_rate"],
                    "accuracy": r["accuracy"],
                })
        if self.bye_player:
            winners.append(self.bye_player)
            self.bye_player = None
        self.alive = winners

    def can_continue(self) -> bool:
        return len(self.alive) >= 2

    def round_name(self) -> str:
        n = len(self.alive)
        return "决赛" if n <= 2 else f"{n}强"

    def set_next_texts(self, texts: list[str]):
        self._custom_texts = texts

    def get_next_text(self, idx: int) -> str:
        if hasattr(self, '_custom_texts') and idx < len(self._custom_texts):
            return self._custom_texts[idx]
        if self.tm:
            return self.tm.pick_random()
        return ""

    def get_match_for(self, pid: str) -> Optional[Match]:
        for m in reversed(self.matches):
            if not m.finished and (m.p1.id == pid or m.p2.id == pid):
                return m
        return None

    def finish(self) -> list:
        # 遍历所有比赛，收集所有选手（已淘汰的+存活的）
        seen = set()
        for m in self.matches:
            for p, pid in [(m.p1, m.p1.id), (m.p2, m.p2.id)]:
                if pid not in seen:
                    seen.add(pid)
                    r = m.get_result(pid).to_dict()
                    self.ranking.append({
                        "name": p.name,
                        "score": r["score"],
                        "completion": r["completion_rate"],
                        "accuracy": r["accuracy"],
                    })
        # 去重（same player in multiple rounds），保留最新一场的分数
        seen_names = set()
        deduped = []
        for rr in reversed(self.ranking):
            if rr["name"] not in seen_names:
                seen_names.add(rr["name"])
                deduped.append(rr)
        deduped.sort(key=lambda x: x["score"], reverse=True)
        return [
            {"rank": i + 1, "name": r["name"],
             "score": round(r["score"], 1),
             "completion": round(r["completion"], 1),
             "accuracy": round(r["accuracy"], 1)}
            for i, r in enumerate(deduped)
        ]

    def reset(self):
        self.alive = []
        self.matches = []
        self.current_round = 0
        self.total_rounds = 0
        self.ranking = []
        self.used_texts = []
        self.bye_player = None
