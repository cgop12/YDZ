# TypeBattle 代码重构规划 (REFACTORING)

> 本文档详细描述 TypeBattle 项目的代码重构计划，旨在提升代码质量、可维护性和可测试性。

---

## 📊 重构概述

### 当前问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 服务端 main.py 超过 1350 行 | 难以维护和理解 | P0 |
| 模块边界不清晰 | 高耦合，难以测试 | P1 |
| 缺少单元测试 | 难以保证代码质量 | P1 |
| 配置硬编码 | 不够灵活 | P2 |

### 重构目标

```
┌─────────────────────────────────────────────────────────────┐
│                    重构目标                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  可维护性      ───▶    模块化拆分，降低复杂度                │
│                                                              │
│  可测试性      ───▶    解耦依赖，支持单元测试                 │
│                                                              │
│  可扩展性      ───▶    清晰接口，便于功能扩展                 │
│                                                              │
│  可读性        ───▶    合理命名，完整文档                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 重构范围

| 组件 | 当前行数 | 目标行数 | 拆分模块数 |
|------|---------|---------|-----------|
| server/main.py | ~1350 | < 500 | 5 |
| common/models.py | ~220 | ~220 | 保持 |
| common/protocol.py | ~130 | ~130 | 保持 |

---

## 📁 重构实施计划

### 阶段 1: 基础设施准备

**目标**: 建立测试框架和依赖注入基础

```
时间: 1-2 天
依赖: 无
风险: 低
```

#### 1.1 创建项目配置文件

```yaml
# pyproject.toml
[project]
name = "typebattle"
version = "1.1.0"
requires-python = ">=3.9"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-v --cov=. --cov-report=term-missing"

[tool.black]
line-length = 120
target-version = ['py39']
include = '\.pyi?$'

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

#### 1.2 创建目录结构

```
server/
├── main.py              # 入口（精简后）
├── config.py            # 新增: 配置管理
├── __init__.py
├── game/                # 新增: 游戏逻辑
│   ├── __init__.py
│   ├── tournament.py    # 拆分: 淘汰赛管理
│   ├── match.py         # 拆分: 比赛逻辑
│   ├── player.py        # 拆分: 玩家管理
│   ├── scoring.py       # 拆分: 计分引擎
│   └── text_manager.py  # 拆分: 文本管理
├── network/             # 新增: 网络层
│   ├── __init__.py
│   ├── websocket_server.py  # 拆分: WebSocket 服务
│   ├── udp_broadcast.py     # 拆分: UDP 广播
│   ├── message_handler.py   # 拆分: 消息处理
│   └── session_manager.py   # 拆分: 会话管理
├── ui/                  # 新增: UI 层
│   ├── __init__.py
│   ├── main_window.py   # 保留: 主窗口
│   └── panels/          # 新增: UI 面板
│       ├── __init__.py
│       ├── player_panel.py
│       ├── game_panel.py
│       └── control_panel.py
└── tests/               # 新增: 测试
    ├── __init__.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_game/
    │   └── test_network/
    └── fixtures/
```

#### 1.3 添加 __init__.py

```python
# server/game/__init__.py
"""游戏逻辑模块"""

from .player import Player, PlayerManager
from .match import Match, MatchManager
from .tournament import Tournament, TournamentManager
from .scoring import ScoringEngine
from .text_manager import TextManager

__all__ = [
    "Player",
    "PlayerManager", 
    "Match",
    "MatchManager",
    "Tournament",
    "TournamentManager",
    "ScoringEngine",
    "TextManager",
]
```

### 阶段 2: 服务端模块拆分

**目标**: 将 main.py 拆分为独立模块

```
时间: 3-5 天
依赖: 阶段 1
风险: 中
```

#### 2.1 拆分 game 模块

**从 main.py 提取**:
- Player 类管理
- Match 类管理
- Tournament 类管理
- 计分逻辑
- 文本管理

**新文件: server/game/player.py**

```python
"""玩家管理模块"""

from typing import Optional
from common.models import Player as ModelPlayer

class PlayerManager:
    """玩家管理器"""
    
    def __init__(self):
        self._players: dict[str, ModelPlayer] = {}
        self._admin_id: Optional[str] = None
    
    def add_player(self, name: str) -> tuple[str, str]:
        """添加玩家，返回 (player_id, error_msg)"""
        # 实现...
    
    def remove_player(self, player_id: str) -> None:
        """移除玩家"""
        # 实现...
    
    def get_player(self, player_id: str) -> Optional[ModelPlayer]:
        """获取玩家"""
        return self._players.get(player_id)
    
    def list_players(self) -> list[dict]:
        """获取玩家列表"""
        return [p.to_dict() for p in self._players.values()]
    
    @property
    def admin_id(self) -> Optional[str]:
        return self._admin_id
    
    @property
    def count(self) -> int:
        return len(self._players)
```

**新文件: server/game/scoring.py**

```python
"""计分引擎模块"""

from typing import NamedTuple
from common.models import WEIGHT_COMPLETION, WEIGHT_ACCURACY, WEIGHT_SPEED, BASE_SPEED

class ScoreResult(NamedTuple):
    """得分结果"""
    score: float
    completion_rate: float
    accuracy: float
    speed_score: float

class ScoringEngine:
    """计分引擎"""
    
    @staticmethod
    def calculate(
        completed: int, 
        total: int, 
        errors: int, 
        elapsed: float
    ) -> ScoreResult:
        """
        计算得分
        
        公式: 完成率×60% + 正确率×30% + 速度得分×10%
        """
        # 完成率
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # 正确率
        accuracy = ((completed - errors) / completed * 100) if completed > 0 else 0
        
        # 速度得分
        speed = (completed / max(elapsed, 0.1)) / BASE_SPEED * 100
        speed_score = min(100, speed)
        
        # 总分
        score = (
            completion_rate * WEIGHT_COMPLETION +
            accuracy * WEIGHT_ACCURACY +
            speed_score * WEIGHT_SPEED
        )
        
        return ScoreResult(
            score=round(score, 1),
            completion_rate=round(completion_rate, 1),
            accuracy=round(accuracy, 1),
            speed_score=round(speed_score, 1)
        )
```

**新文件: server/game/text_manager.py**

```python
"""文本管理模块"""

import json
import os
import random
from typing import Optional

class TextManager:
    """打字文本管理器"""
    
    def __init__(self, data_dir: str = "data"):
        self._data_dir = data_dir
        self._texts: list[str] = []
        self._load_texts()
    
    def _load_texts(self) -> None:
        """加载文本库"""
        texts_file = os.path.join(self._data_dir, "texts.json")
        if os.path.exists(texts_file):
            with open(texts_file, "r", encoding="utf-8") as f:
                self._texts = json.load(f)
        else:
            # 默认文本
            self._texts = [
                "春眠不觉晓，处处闻啼鸟。",
                "床前明月光，疑是地上霜。",
                # ...
            ]
    
    def pick_random(self) -> str:
        """随机选择一个文本"""
        return random.choice(self._texts)
    
    def pick_batch(self, count: int, exclude: list[str] = None) -> list[str]:
        """随机选择多个文本"""
        exclude = exclude or []
        available = [t for t in self._texts if t not in exclude]
        return random.sample(available or self._texts, min(count, len(available or self._texts)))
```

#### 2.2 拆分 network 模块

**新文件: server/network/message_handler.py**

```python
"""消息处理器"""

import asyncio
from typing import Callable, Awaitable
from common.protocol import decode, require

class MessageHandler:
    """消息处理器基类"""
    
    def __init__(self):
        self._handlers: dict[str, Callable] = {}
    
    def register(self, msg_type: str, handler: Callable[[dict], Awaitable[None]]):
        """注册消息处理器"""
        self._handlers[msg_type] = handler
    
    async def handle(self, raw_message: str) -> None:
        """处理消息"""
        msg = decode(raw_message)
        if msg is None:
            return
        
        msg_type = msg.get("type")
        handler = self._handlers.get(msg_type)
        
        if handler:
            await handler(msg)
        else:
            # 未知消息类型
            pass
```

#### 2.3 精简 main.py

重构后的 main.py 应该只包含：

```python
"""打字对战服务端 - 精简后的入口"""

import sys
import asyncio
from PyQt6.QtWidgets import QApplication

from server.config import ServerConfig
from server.game import TournamentManager, TextManager
from server.network import WebSocketServer, UDPBroadcaster
from server.ui import MainWindow
from common.logger import setup_logger, get_logger

async def main_async(config: ServerConfig):
    """异步主函数"""
    logger = get_logger("server")
    
    # 初始化组件
    text_manager = TextManager(config.data_dir)
    tournament_manager = TournamentManager(text_manager)
    
    # 初始化网络
    ws_server = WebSocketServer(
        host=config.host,
        port=config.port,
        tournament_manager=tournament_manager,
    )
    udp_broadcaster = UDPBroadcaster(
        port=config.udp_port,
        ws_port=config.port,
    )
    
    # 启动网络服务
    async with asyncio.TaskGroup() as tg:
        tg.create_task(ws_server.start())
        tg.create_task(udp_broadcaster.start())
    
    logger.info(f"服务已启动: ws://{config.host}:{config.port}")

def main():
    """主入口"""
    # 初始化日志
    setup_logger("server", "server")
    logger = get_logger("server")
    
    # 加载配置
    config = ServerConfig.from_args()
    
    # 启动 Qt 应用
    app = QApplication(sys.argv)
    
    # 创建主窗口（用于管理界面）
    window = MainWindow()
    window.show()
    
    # 在事件循环中运行异步代码
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main_async(config))
    finally:
        loop.close()

if __name__ == "__main__":
    main()
```

---

## 📋 具体拆分清单

### main.py 当前内容拆分

| 行号范围 | 内容类型 | 拆分目标 |
|---------|---------|---------|
| 1-50 | 导入语句 | 保持 |
| 51-150 | 配置常量 | → config.py |
| 151-250 | 图标加载 | → ui/utils.py |
| 251-400 | Player/PlayerManager | → game/player.py |
| 401-550 | TextManager | → game/text_manager.py |
| 551-700 | Match 类 | → game/match.py |
| 701-900 | Tournament 类 | → game/tournament.py |
| 901-1000 | 计时器逻辑 | → game/timer.py |
| 1001-1150 | UI 组件创建 | → ui/panels/*.py |
| 1151-1250 | 网络回调 | → network/message_handler.py |
| 1251-1350 | 主事件循环 | → main.py (简化) |

---

## 🧪 测试策略

### 重构前测试

确保现有功能在重构后保持不变：

```bash
# 重构前执行
pytest tests/ --cov=common --cov-report=html
```

### 重构后验证

```bash
# 重构后执行
pytest tests/ --cov=server --cov-report=term-missing
```

### 关键测试点

| 模块 | 测试内容 | 优先级 |
|------|---------|--------|
| scoring | 计分公式正确性 | P0 |
| player | 玩家增删改查 | P0 |
| match | 胜负判定 | P0 |
| tournament | 轮次生成 | P0 |
| protocol | 消息编码解码 | P1 |

---

## ⚠️ 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 拆分过程中引入 bug | 高 | 保持原有逻辑不变，仅改变组织方式 |
| 循环依赖 | 中 | 使用接口抽象解耦 |
| 性能下降 | 低 | 保持异步架构，使用轻量级抽象 |
| 测试覆盖不足 | 中 | 重构前先增加测试 |

---

## 📅 时间计划

```
Week 1: 基础设施
├── Day 1-2: 项目结构 + 测试框架
├── Day 3-4: common 模块测试
└── Day 5: review + 合并

Week 2-3: 服务端拆分
├── Day 6-8: game 模块拆分
├── Day 9-11: network 模块拆分
├── Day 12-14: ui 模块整理
└── Day 15: review + 合并

Week 4: 集成测试
├── Day 16-18: 集成测试
├── Day 19-20: 缺陷修复
└── Day 21: 最终 review + 发布
```

---

## ✅ 重构验收标准

- [ ] main.py 行数 < 500
- [ ] 核心模块测试覆盖 > 80%
- [ ] 所有现有功能正常工作
- [ ] 无性能下降 (> 5%)
- [ ] 文档已更新

---

## 📝 参考资料

- [Python 项目结构最佳实践](https://docs.python-guide.org/writing/structure/)
- [Pytest 官方文档](https://docs.pytest.org/)
- [PyQt6 官方文档](https://doc.qt.io/qtforpython/)

---

*重构计划版本: v1.0*
*最后更新: 2026-05-12*
