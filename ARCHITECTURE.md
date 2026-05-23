# TypeBattle 架构设计文档

| 文档信息 | |
|---------|---|
| **项目名称** | TypeBattle（打字对战） |
| **文档版本** | v1.0 |
| **创建日期** | 2026-05-12 |
| **文档状态** | 正式版 |

---

## 一、系统架构概览

### 1.1 架构模式

```
┌─────────────────────────────────────────────────────────────────┐
│                      TypeBattle 系统架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐              ┌──────────────┐                 │
│  │   Client A   │              │   Client B   │                 │
│  │  (PyQt6 UI)  │              │  (PyQt6 UI)  │                 │
│  └──────┬───────┘              └──────┬───────┘                 │
│         │                             │                          │
│         │    WebSocket + UDP          │                          │
│         └─────────┬───────────────────┘                          │
│                   │                                               │
│  ┌────────────────▼────────────────┐                           │
│  │          Server (PyQt6)           │                           │
│  │  ┌─────────┐  ┌─────────┐        │                           │
│  │  │  Game   │  │Network  │        │                           │
│  │  │ Engine  │  │ Handler │        │                           │
│  │  └─────────┘  └─────────┘        │                           │
│  │  ┌─────────┐  ┌─────────┐        │                           │
│  │  │Tournament│ │Scoring │        │                           │
│  │  │ Manager │  │ Engine │        │                           │
│  │  └─────────┘  └─────────┘        │                           │
│  └─────────────────────────────────┘                           │
│                                                                  │
│  ┌──────────────────────────────────────┐                       │
│  │              Common Module             │                       │
│  │   protocol.py │ models.py │ logger.py  │                       │
│  └──────────────────────────────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 组件关系图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           客户端组件                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐          │
│  │  Login  │────▶│ Lobby   │────▶│ Battle  │────▶│ Result  │          │
│  │  Page   │     │  Page   │     │  Page   │     │  Page   │          │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘          │
│       │               │               │               │              │
│       └───────────────┴───────────────┴───────────────┘              │
│                              │                                       │
│                    ┌─────────▼─────────┐                             │
│                    │    GameClient     │                             │
│                    │  (WebSocket)      │                             │
│                    └─────────┬─────────┘                             │
│                              │                                       │
│                    ┌─────────▼─────────┐                             │
│                    │  UDP Discovery    │                             │
│                    │  (Auto-Find)     │                             │
│                    └───────────────────┘                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                           服务端组件                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                     MainWindow (PyQt6)                    │       │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │       │
│  │  │  UI Panel   │  │ Game State │  │ Admin Ctrl │        │       │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │       │
│  └──────────────────────────────────────────────────────────┘       │
│                              │                                       │
│                    ┌─────────▼─────────┐                             │
│                    │   WebSocket      │                             │
│                    │   Server         │                             │
│                    │  (asyncio)       │                             │
│                    └─────────┬─────────┘                             │
│                              │                                       │
│  ┌──────────────────────────┴──────────────────────────┐           │
│  │                                                      │           │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │           │
│  │  │  Tournament  │  │    Match     │  │  Player   │  │           │
│  │  │   Manager    │──│   Manager    │──│  Manager  │  │           │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │           │
│  │                                                      │           │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │           │
│  │  │    Text      │  │   Scoring    │  │  Network  │  │           │
│  │  │   Manager    │  │    Engine    │  │  Handler  │  │           │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │           │
│  │                                                      │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
│                    ┌─────────▼─────────┐                             │
│                    │  UDP Discovery    │                             │
│                    │  (Broadcast)      │                             │
│                    └───────────────────┘                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、项目结构

### 2.1 当前目录结构

```
D:\type_battle\
├── client/                         # 客户端模块
│   ├── main.py                     # 客户端入口
│   ├── network.py                  # WebSocket 客户端
│   ├── protocol.py                 # 客户端协议（已迁移到 common）
│   ├── widgets.py                  # 通用 UI 组件
│   ├── connection_diagnostic.py    # 网络诊断工具
│   ├── pages/                      # 页面模块
│   │   ├── login.py                # 登录页
│   │   ├── lobby.py                # 大厅页
│   │   ├── battle.py               # 比赛页
│   │   ├── result.py               # 结果页
│   │   └── overlay.py              # 遮罩层
│   ├── ui/                         # UI 资源
│   ├── utils/                      # 工具函数
│   ├── build/                      # PyInstaller 构建目录
│   └── dist/                       # 打包输出目录
│
├── server/                         # 服务端模块
│   ├── main.py                     # 服务端入口 (1350+ 行)
│   ├── network_diag.py              # 网络诊断
│   ├── protocol.md                 # 协议文档
│   ├── data/                       # 游戏数据（打字文本等）
│   ├── build/                      # PyInstaller 构建目录
│   └── dist/                       # 打包输出目录
│
├── common/                         # 共享模块
│   ├── __init__.py                 # 模块初始化
│   ├── protocol.py                 # 统一消息协议
│   ├── models.py                   # 数据模型 (Player, Match, Tournament)
│   └── logger.py                   # 日志模块
│
├── logs/                           # 日志目录
├── client.ico                      # 客户端图标
├── server.ico                      # 服务端图标
├── run_client.bat                  # 启动客户端
├── run_server.bat                  # 启动服务端
├── 打包说明.md                      # 打包指南
├── 局域网连接问题解决指南.md         # 连接问题文档
└── SPEC.md                         # 需求规格说明书
```

### 2.2 建议的重构目录结构

```
D:\type_battle\
├── client/                         # 客户端
│   ├── main.py
│   ├── app.py                     # 应用程序类
│   ├── config.py                  # 客户端配置
│   ├── network/
│   │   ├── __init__.py
│   │   ├── client.py              # WebSocket 客户端
│   │   └── discovery.py           # UDP 发现
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── base.py                # 基础页面类
│   │   ├── login.py
│   │   ├── lobby.py
│   │   ├── battle.py
│   │   └── result.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   └── common.py              # 通用组件
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── tests/
│       ├── __init__.py
│       ├── test_network.py
│       └── test_pages.py
│
├── server/                         # 服务端
│   ├── main.py                     # 入口（精简后）
│   ├── config.py                   # 服务端配置
│   ├── game/
│   │   ├── __init__.py
│   │   ├── tournament.py          # 淘汰赛管理
│   │   ├── match.py               # 比赛逻辑
│   │   ├── player.py              # 玩家管理
│   │   ├── scoring.py             # 计分引擎
│   │   └── text_manager.py        # 文本管理
│   ├── network/
│   │   ├── __init__.py
│   │   ├── websocket_server.py    # WebSocket 服务
│   │   ├── udp_broadcast.py       # UDP 广播
│   │   ├── message_handler.py    # 消息处理
│   │   └── session_manager.py     # 会话管理
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py        # 主窗口
│   │   └── panels/                # UI 面板
│   ├── data/
│   │   └── texts.json             # 打字文本库
│   └── tests/
│       ├── __init__.py
│       ├── test_game.py
│       └── test_network.py
│
├── common/                         # 共享模块
│   ├── __init__.py
│   ├── protocol.py                # 消息协议
│   ├── models.py                  # 数据模型
│   ├── constants.py               # 常量定义
│   └── logger.py                  # 日志
│
├── docs/                           # 文档目录
│   ├── SPEC.md
│   ├── ARCHITECTURE.md
│   ├── PROTOCOL.md
│   └── ROADMAP.md
│
├── scripts/                        # 脚本目录
│   ├── build_client.bat
│   ├── build_server.bat
│   └── setup_firewall.bat
│
├── CHANGELOG.md
├── CONTRIBUTING.md
├── README.md
└── requirements.txt
```

---

## 三、核心模块设计

### 3.1 协议层 (common/protocol.py)

**职责**: 统一管理客户端与服务端之间的通信协议

```python
# 消息类型常量
C_JOIN = "join"                      # 客户端请求加入
S_JOIN_ACK = "join_ack"             # 服务端确认加入
S_PLAYER_LIST = "player_list"       # 玩家列表更新
C_READY = "ready"                   # 玩家准备
S_READY_STATUS = "ready_status"    # 准备状态
S_COUNTDOWN = "countdown"           # 赛前倒计时
S_MATCH_BEGIN = "match_begin"       # 比赛开始
C_KEYSTROKE = "keystroke"           # 逐字按键
S_KEYSTROKE_ACK = "keystroke_ack"  # 按键确认
S_TIME_SYNC = "time_sync"          # 时间同步
C_PROGRESS = "progress"             # 进度上报
S_ROUND_END = "round_end"          # 轮次结束
S_FINAL_RANKING = "final_ranking"   # 最终排名
C_PAUSE_REQUEST = "pause_request"  # 暂停请求
S_PAUSE_BROADCAST = "pause_broadcast"  # 暂停广播
C_RESUME_REQUEST = "resume_request"    # 恢复请求
S_RESUME_BROADCAST = "resume_broadcast" # 恢复广播
C_RECONNECT = "reconnect"          # 断线重连
S_FULL_STATE = "full_state_snapshot"  # 完整状态快照
S_PING = "ping"                    # 心跳
C_PONG = "pong"                    # 心跳响应
S_ERROR = "error"                  # 错误消息
```

**设计原则**:
- 所有消息类型集中定义，便于维护
- 提供编码/解码辅助函数
- 支持 JSON 序列化

### 3.2 数据模型层 (common/models.py)

**职责**: 定义核心业务实体的数据结构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Player      │     │      Match      │     │   Tournament    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id: str         │◀───▶│ p1: Player      │     │ players: dict  │
│ name: str       │     │ p2: Player      │────▶│ admin_id: str   │
│ is_admin: bool  │     │ text: str       │     │ alive: list     │
│                 │     │ winner: Player  │     │ matches: list  │
│ to_dict()       │     │ loser: Player   │     │ current_round   │
└─────────────────┘     │ finished: bool   │     │ total_rounds    │
                        │                   │     │ ranking: list   │
                        │ update()          │     │ used_texts      │
                        │ decide_winner()   │     │                 │
                        │ get_result()      │     │ create_round()  │
                        └─────────────────┘     │ finish_round()  │
                                                 └─────────────────┘
```

**MatchResult 计算**:
```
score = 完成率×60% + 正确率×30% + 速度得分×10%
```

### 3.3 网络层 (server/network_handler.py)

**职责**: 处理 WebSocket 连接和消息路由

```python
class NetworkHandler:
    """WebSocket 网络处理器"""
    
    # 连接管理
    def handle_connect(websocket)    # 新连接
    def handle_disconnect(player_id)  # 断开连接
    def handle_message(websocket, message)  # 消息处理
    
    # 消息路由
    def route_join(data)            # 处理加入
    def route_ready(data)           # 处理准备
    def route_keystroke(data)       # 处理按键
    def route_progress(data)        # 处理进度
    def route_admin(action)         # 处理管理操作
    
    # 广播
    def broadcast_player_list()    # 广播玩家列表
    def broadcast_time_sync()       # 广播时间同步
    def broadcast_match_result()    # 广播比赛结果
```

### 3.4 游戏引擎 (server/game/)

**职责**: 管理比赛流程和游戏逻辑

```
TournamentManager
├── 管理所有玩家和比赛状态
├── 创建和管理淘汰赛轮次
├── 处理轮空（Walkover）
└── 计算最终排名

MatchManager
├── 管理当前比赛
├── 验证输入正确性
├── 跟踪进度
└── 决定胜负

ScoringEngine
├── 计算完成率
├── 计算正确率
├── 计算速度得分
└── 计算总分
```

---

## 四、消息流设计

### 4.1 连接流程

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client  │                    │  Server  │                    │   UDP    │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                              │                              │
     │  UDP: broadcast discover ────────────────────────────────────▶
     │                              │                              │
     │                              │  UDP: {ip, port, room} ◀─────
     │  WS: connect(ip, 8888) ────▶│                              │
     │                              │                              │
     │  WS: {type:join, name:xxx} ─▶│                              │
     │                              │                              │
     │                              │  处理加入逻辑                │
     │                              │  • 验证名字唯一性            │
     │                              │  • 分配 player_id           │
     │                              │  • 设置第一个用户为管理员    │
     │                              │                              │
     │  {type:join_ack, player_id} ◀─│                            │
     │                              │                              │
     │  {type:player_list,...} ◀─────│                            │
     │                              │                              │
     ▼                              ▼                              ▼
```

### 4.2 比赛流程

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│  Client  │          │  Server  │          │  Client  │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                     │
     │  ready {ready:true} │                     │
     │────────────────────▶│                     │
     │                     │                     │
     │                     │  ready_status {all_ready:false}
     │◀─────────────────────│                     │
     │                     │                     │
     │                     │  ... (等待所有玩家)   │
     │                     │                     │
     │                     │  admin_start        │
     │                     │◀────────────────────│
     │                     │                     │
     │  countdown {5}      │                     │
     │◀─────────────────────│                     │
     │                     │                     │
     │  countdown {4}      │                     │
     │◀─────────────────────│                     │
     │                     │                     │
     │  countdown {3}      │                     │
     │◀─────────────────────│                     │
     │                     │                     │
     │  match_begin {...}   │                     │
     │◀─────────────────────│                     │
     │                     │                     │
     │  [开始打字]          │                     │
     │                     │                     │
     │  keystroke {index:0,char:春}              │
     │────────────────────▶│                     │
     │                     │                     │
     │  keystroke_ack {index:0,correct:true}    │
     │◀─────────────────────│                     │
     │                     │                     │
     │  time_sync {remaining_ms:37500}           │
     │◀─────────────────────│                     │
     │                     │                     │
     │  [继续打字...]       │                     │
     │                     │                     │
     ▼                     ▼                     ▼
```

### 4.3 暂停/恢复流程

```
┌──────────┐          ┌──────────┐
│  Admin   │          │  Server  │          [所有客户端]
│  Client  │          │          │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                     │
     │  pause_request      │                     │
     │────────────────────▶│                     │
     │                     │                     │
     │                     │  pause_broadcast     │
     │                     │────────────────────▶│
     │                     │                     │
     │                     │  time_sync paused    │
     │                     │────────────────────▶│
     │                     │                     │
     │                     │  [忽略所有 keystroke]│
     │                     │                     │
     │  resume_request     │                     │
     │────────────────────▶│                     │
     │                     │                     │
     │                     │  resume_broadcast   │
     │                     │────────────────────▶│
     │                     │                     │
     │                     │  time_sync (继续)    │
     │                     │────────────────────▶│
     │                     │                     │
     ▼                     ▼                     ▼
```

---

## 五、网络协议详解

### 5.1 WebSocket 消息格式

```json
// 单条消息格式
{
  "type": "消息类型",
  "字段1": "值1",
  "字段2": "值2"
}

// 传输方式
- 编码: UTF-8
- 分隔: JSON + 换行符 (\n)
- 示例:
{"type":"join","name":"张三"}\n
{"type":"ready","ready":true}\n
```

### 5.2 UDP 发现协议

```python
# 客户端发送
broadcast("type_battle_discover", port=23333)

# 可选：查询指定房间
broadcast("type_battle_discover?room=1234", port=23333)

# 服务器响应
{
    "ip": "192.168.1.100",
    "port": 8888,
    "room": "1234",
    "count": 12,
    "max": 32
}
```

### 5.3 心跳机制

```
服务端: 每 2 秒发送
{
  "type": "ping",
  "server_time": 12345678.9
}

客户端: 立即响应
{
  "type": "pong"
}

断线判定: 5 秒未收到 pong → 标记离线
```

---

## 六、数据存储

### 6.1 服务端数据

| 数据 | 存储方式 | 说明 |
|------|---------|------|
| 打字文本 | JSON 文件 `data/texts.json` | 预置打字材料 |
| 玩家状态 | 内存 (dict) | 断线 10 秒内保留 |
| 比赛记录 | 内存 | 仅运行时有效 |
| 日志 | 文件 `logs/server_YYYY-MM-DD.log` | 按日期滚动 |

### 6.2 客户端数据

| 数据 | 存储方式 | 说明 |
|------|---------|------|
| 配置 | 无持久化 | 每次启动重新输入 |
| 日志 | 文件 `logs/client_YYYY-MM-DD.log` | 按日期滚动 |
| 崩溃记录 | 文件 `logs/crash_*.log` | 自动生成 |

---

## 七、部署架构

### 7.1 单机部署

```
┌─────────────────────────────────────────┐
│              局域网环境                   │
│                                          │
│  ┌─────────────┐                       │
│  │   Server     │  IP: 192.168.1.100   │
│  │  Port: 8888  │  UDP: 23333          │
│  └─────────────┘                       │
│          │                              │
│   ┌──────┴──────┐                      │
│   │    交换机/路由器    │               │
│   └──────┬──────┘                      │
│          │                              │
│   ┌──────┴────────────────┐             │
│   │                       │             │
│ ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐            │
│ │C1 │  │C2 │  │C3 │  │C4 │  ...       │
│ └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘            │
│   │      │      │      │               │
└───┴──────┴──────┴──────┴───────────────┘
```

### 7.2 防火墙配置

| 组件 | 协议 | 端口 | 方向 | 说明 |
|------|------|------|------|------|
| 服务端 | TCP | 8888 | 入站 | WebSocket 连接 |
| 服务端 | UDP | 23333 | 入站/出站 | 服务发现 |
| 客户端 | TCP | 8888 | 出站 | 连接服务器 |

---

## 八、错误处理策略

### 8.1 服务端错误处理

```python
try:
    # 业务逻辑
except ValidationError as e:
    send_error("INVALID_MESSAGE", str(e))
except PermissionError as e:
    send_error("NOT_ADMIN", str(e))
except GameStateError as e:
    send_error("GAME_STATE_ERROR", str(e))
except Exception as e:
    log_error(e)
    send_error("SERVER_ERROR", "Internal error")
```

### 8.2 客户端错误处理

```python
# 网络断开
on_connection_lost():
    show_overlay("与服务器断开连接")
    enable_reconnect_button()

# 错误消息
on_error(code, message):
    if code == "NAME_TAKEN":
        show_error("该名字已被占用，请换一个名字")
    elif code == "ROOM_FULL":
        show_error("房间已满，请稍后再试")
    else:
        show_error(f"错误: {message}")

# 崩溃处理
sys.excepthook = global_exception_handler
# 记录日志，显示友好提示
```

---

## 九、扩展性设计

### 9.1 预留扩展点

| 功能 | 当前状态 | 扩展方向 |
|------|---------|---------|
| AI 对战 | 未实现 | 添加 BotPlayer 类 |
| 观战模式 | 未实现 | 添加 Spectator 角色 |
| 自定义文本 | 未实现 | 添加 TextManager.load_custom() |
| 计分规则 | 固定 | 添加 ScoringStrategy 接口 |
| 排行榜历史 | 未实现 | 添加 Database 支持 |

### 9.2 插件化设计

```
common/
├── protocol.py        # 固定协议（扩展需新增消息类型）
├── models.py          # 固定模型（扩展可继承）
└── logger.py          # 日志框架

server/
├── game/
│   ├── tournament.py  # 可扩展：自定义赛制
│   ├── match.py       # 可扩展：自定义规则
│   └── scoring.py     # 可扩展：自定义计分
└── data/
    └── texts.json     # 可扩展：自定义题库
```

---

## 十、附录

### A. 依赖关系图

```
requirements.txt
├── pyqt6           # GUI 框架
├── websockets      # WebSocket 通信
├── psutil          # 进程优先级（可选）
└── pyinstaller     # 打包工具（仅构建时）
```

### B. 环境变量

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `TYPEBATTLE_PORT` | 8888 | WebSocket 端口 |
| `TYPEBATTLE_UDP_PORT` | 23333 | UDP 发现端口 |
| `TYPEBATTLE_MAX_PLAYERS` | 32 | 最大玩家数 |
| `TYPEBATTLE_TEXT_DIR` | data/ | 文本目录 |

---

*文档版本历史*
| 版本 | 日期 | 修改内容 |
|------|------|---------|
| v1.0 | 2026-05-12 | 初始版本 |
