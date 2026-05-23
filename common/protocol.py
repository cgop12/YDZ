"""统一消息协议层 — 客户端与服务端共享 (紧凑格式)"""

import json
import time


def encode(msg: dict) -> str:
    return json.dumps(msg, ensure_ascii=False, separators=(',', ':'))

def decode(raw: str | bytes):
    try:
        return json.loads(raw.strip())
    except (json.JSONDecodeError, AttributeError):
        return None


# ─── Client → Server (compact single-char keys) ───
C_JOIN         = "j"
C_PROGRESS     = "p"
C_PONG         = "o"
C_ADMIN_START  = "as"
C_PAUSE_REQUEST   = "pr"
C_RESUME_REQUEST  = "rr"
C_ADMIN_END    = "ae"
C_RECONNECT    = "rc"
C_READY        = "rd"

# ─── Server → Client (compact single-char keys) ───
S_JOIN_ACK          = "ja"
S_PLAYER_LIST       = "pl"
S_COUNTDOWN         = "cd"
S_MATCH_BEGIN       = "mb"
S_ROUND_END         = "re"
S_FINAL_RANKING     = "fr"
S_PAUSE_BROADCAST   = "pb"
S_RESUME_BROADCAST  = "rb"
S_FORCE_END         = "fe"
S_TIME_SYNC         = "ts"
S_READY_STATUS      = "rs"
S_FULL_STATE        = "fs"
S_PING              = "pi"
S_ERROR             = "er"


def _m(**kw): return encode(kw)


# ─── Server messages ───

def s_join_ack(player_id: str, name: str, players: list, count: int, room: str) -> str:
    return _m(t=S_JOIN_ACK, p=player_id, n=name, s=players)

def s_player_list(players: list, count: int) -> str:
    return _m(t=S_PLAYER_LIST, p=players)

def s_countdown(seconds: int) -> str:
    return _m(t=S_COUNTDOWN, s=seconds)

def s_match_begin(round_num: int, round_name: str, opponent: str, text: str,
                  text_length: int, time_limit: int, pinyin_text: str = "") -> str:
    return _m(t=S_MATCH_BEGIN, r=round_num, n=round_name, o=opponent,
              x=text, l=text_length, tt=time_limit, p=pinyin_text)

def s_round_end(winner: str, my_result: dict, opponent_result: dict) -> str:
    return _m(t=S_ROUND_END, w=winner, r1=my_result, r2=opponent_result)

def s_final_ranking(ranking: list) -> str:
    return _m(t=S_FINAL_RANKING, r=ranking)

def s_pause_broadcast(remaining_ms: int) -> str:
    return _m(t=S_PAUSE_BROADCAST, r=int(remaining_ms))

def s_resume_broadcast(remaining_ms: int) -> str:
    return _m(t=S_RESUME_BROADCAST, r=int(remaining_ms))

def s_time_sync(remaining_ms: int, paused: bool) -> str:
    return _m(t=S_TIME_SYNC, r=int(remaining_ms), p=paused)

def s_ready_status(players: dict, all_ready: bool) -> str:
    return _m(t=S_READY_STATUS, r=players, a=all_ready)

def s_full_state(player_id: str, remaining_ms: int, paused: bool,
                 round_num: int, round_name: str, opponent: str,
                 text: str, text_length: int, time_limit: int,
                 my_progress: dict, opponent_progress: dict, players: list,
                 pinyin_text: str = "") -> str:
    return _m(t=S_FULL_STATE, p=player_id, r=remaining_ms, u=paused,
              n=round_num, m=round_name, o=opponent,
              x=text, l=text_length, tt=time_limit,
              y=my_progress, z=opponent_progress, s=players,
              h=pinyin_text)

def s_force_end(reason: str) -> str:
    return _m(t=S_FORCE_END, r=reason)

def s_error(code: str, message: str) -> str:
    return _m(t=S_ERROR, c=code, m=message)

def s_ping() -> str:
    return _m(t=S_PING, s=time.time())
