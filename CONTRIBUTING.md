# TypeBattle 贡献指南 (CONTRIBUTING)

感谢您对 TypeBattle 项目的关注！本文档将帮助您了解如何参与项目贡献。

---

## 📋 目录

- [行为准则](#行为准则)
- [快速开始](#快速开始)
- [开发环境](#开发环境)
- [代码规范](#代码规范)
- [提交流程](#提交流程)
- [测试指南](#测试指南)
- [文档贡献](#文档贡献)
- [问题反馈](#问题反馈)

---

## 🏆 行为准则

我们期望所有贡献者都能遵守以下准则：

### ✅ 应该做的

- 使用友好、包容的语言
- 尊重不同的观点和经验
- 专注于为项目带来积极贡献
- 对新用户提供耐心和帮助
- 协作解决分歧时保持建设性

### ❌ 不应该做的

- 人身攻击或贬低性评论
- 公开或私下的骚扰
- 未经允许发布他人私人信息
- 其他不专业的行为

---

## 🚀 快速开始

### 1. Fork 项目

点击 GitHub 页面右上角的 **Fork** 按钮，将项目 fork 到您的账户。

### 2. 克隆本地

```bash
# 替换为您的 fork 地址
git clone https://github.com/YOUR_USERNAME/type_battle.git
cd type_battle
```

### 3. 添加上游仓库

```bash
git remote add upstream https://github.com/ORIGINAL_OWNER/type_battle.git
```

### 4. 创建功能分支

```bash
git checkout -b feature/your-feature-name
# 或者
git checkout -b fix/issue-description
```

---

## 💻 开发环境

### 系统要求

| 要求 | 最低版本 | 推荐版本 |
|------|---------|---------|
| 操作系统 | Windows 10 | Windows 11 |
| Python | 3.9 | 3.11+ |
| 内存 | 4GB | 8GB+ |
| 磁盘 | 1GB 可用 | 2GB+ 可用 |

### 安装依赖

```bash
# 克隆仓库后，进入目录
cd D:\type_battle

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# 或
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install pyqt6 websockets psutil pytest pytest-cov

# 安装开发依赖（可选）
pip install black flake8 mypy
```

### 验证安装

```bash
# 测试 Python 版本
python --version
# 应该显示 Python 3.9.x 或更高

# 测试 PyQt6
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"

# 测试 websockets
python -c "import websockets; print('websockets OK')"

# 测试项目导入
cd D:\type_battle
python -c "from common.protocol import encode, decode; print('common OK')"
```

### 运行项目

```bash
# 启动服务端
cd server
python main.py

# 新开终端，启动客户端
cd client
python main.py
```

---

## 📐 代码规范

### Python 代码规范

TypeBattle 项目遵循 **PEP 8** 规范，并使用以下补充规则：

#### 1. 格式化工具配置

我们使用 **Black** 进行代码格式化：

```bash
# 安装 Black
pip install black

# 格式化代码
black server/main.py
black client/main.py

# 检查格式（不修改）
black --check server/main.py
```

#### 2. 代码检查

```bash
# 安装 flake8
pip install flake8

# 运行检查
flake8 server/ --max-line-length=120 --ignore=E203,W503
flake8 client/ --max-line-length=120 --ignore=E203,W503
```

#### 3. 类型检查

```bash
# 安装 mypy
pip install mypy

# 运行类型检查
mypy common/ --ignore-missing-imports
```

### 代码风格规则

#### 命名规范

| 类型 | 规则 | 示例 |
|------|------|------|
| 模块 | 小写下划线 | `network_handler.py` |
| 类 | 大驼峰 | `class TournamentManager` |
| 函数 | 小写下划线 | `def handle_keystroke()` |
| 常量 | 全大写下划线 | `MAX_PLAYERS = 32` |
| 变量 | 小写下划线 | `player_id = "a1b2c3d4"` |
| 私有成员 | 前置下划线 | `self._internal_state` |

#### 文档字符串

所有公共函数和类应包含文档字符串：

```python
def calculate_score(completed: int, errors: int, elapsed: float, total: int) -> float:
    """
    计算打字比赛得分。

    计分公式: 完成率×60% + 正确率×30% + 速度得分×10%

    Args:
        completed: 已完成字数
        errors: 错误次数
        elapsed: 用时（秒）
        total: 总字数

    Returns:
        得分（0-100）

    Example:
        >>> score = calculate_score(18, 2, 60.0, 20)
        >>> round(score, 1)
        85.3
    """
    pass
```

#### 导入顺序

```python
# 1. 标准库
import sys
import os
from datetime import datetime
from typing import Optional

# 2. 第三方库
from PyQt6.QtWidgets import QWidget
from websockets import WebSocketServer

# 3. 本地模块
from common.protocol import encode, decode
from common.models import Player

# 4. 相对导入（如果使用）
from .utils import helper_function
```

### 提交信息规范

提交信息应遵循以下格式：

```
<类型>: <简短描述>

[可选的详细说明]

[可选的关联 Issue]
```

**类型标识**：

| 标识 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加 AI 对战模式` |
| `fix` | 缺陷修复 | `fix: 修复断线重连丢失进度问题` |
| `docs` | 文档更新 | `docs: 更新协议文档` |
| `style` | 代码格式 | `style: 格式化代码` |
| `refactor` | 重构 | `refactor: 拆分 Tournament 类` |
| `test` | 测试相关 | `test: 添加计分测试用例` |
| `chore` | 构建/工具 | `chore: 更新依赖版本` |

**示例**：

```bash
# 好
git commit -m "feat: 添加断线重连状态保留功能

实现 10 秒内的状态保留，允许客户端重连后恢复比赛。
修复了网络不稳定时用户体验差的问题。

Fixes #15"

# 不好
git commit -m "update stuff"
git commit -m "fix bug"
```

---

## 🔄 提交流程

### 1. 同步上游变更

```bash
# 确保在主分支
git checkout main

# 获取上游最新代码
git fetch upstream

# 合并到本地主分支
git merge upstream/main

# 推送更新到您的 fork
git push origin main
```

### 2. 创建您的更改

```bash
# 创建功能分支
git checkout -b feature/your-feature

# 进行开发工作
# ... 编辑代码 ...

# 提交更改
git add .
git commit -m "feat: 添加新功能"
```

### 3. 保持分支同步

在开发过程中，定期同步主分支：

```bash
# 切回主分支
git checkout main
git fetch upstream
git merge upstream/main

# 重新应用您的更改
git checkout feature/your-feature
git rebase main
```

### 4. 推送和创建 PR

```bash
# 推送到您的 fork
git push origin feature/your-feature
```

然后在 GitHub 上创建 Pull Request。

### Pull Request 模板

```markdown
## 描述
<!-- 请简洁描述此 PR 的目的 -->

## 变更类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 代码重构
- [ ] 其他

## 测试
<!-- 请描述您如何测试这些更改 -->

- [ ] 我已测试这些更改
- [ ] 添加了新的测试用例
- [ ] 所有测试都通过了

## 截图/录屏（如果适用）
<!-- 添加 UI 相关的截图或录屏 -->

## 关联 Issue
<!-- 如果此 PR 关联某个 Issue，请引用 -->
Closes #XX
Fixes #XX
```

### 代码审查要点

审查者会关注：

1. **功能正确性** - 代码是否按预期工作？
2. **代码质量** - 是否遵循代码规范？
3. **测试覆盖** - 是否有足够的测试？
4. **文档完整** - 是否更新了相关文档？
5. **性能影响** - 是否影响性能？
6. **向后兼容** - 是否破坏现有功能？

---

## 🧪 测试指南

### 测试框架

我们使用 **pytest** 作为测试框架。

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行所有测试
pytest

# 运行特定目录
pytest tests/unit/
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=. --cov-report=html

# 查看覆盖率
# 打开 htmlcov/index.html
```

### 编写测试

#### 单元测试示例

```python
# tests/unit/test_models.py

import pytest
from common.models import MatchResult, Player, Match

class TestMatchResult:
    """MatchResult 计分测试"""

    def test_perfect_score(self):
        """完美完成：20 字，0 错误，60 秒"""
        result = MatchResult(completed=20, total=20, errors=0, elapsed=60.0)
        score = result.score()
        
        # 完成率 100%, 正确率 100%, 速度 11.1
        assert score == pytest.approx(100.0, rel=0.1)

    def test_with_errors(self):
        """有错误的情况：20 字，2 错误，60 秒"""
        result = MatchResult(completed=20, total=20, errors=2, elapsed=60.0)
        score = result.score()
        
        # 完成率 100%, 正确率 90%, 速度 11.1
        expected = 100 * 0.6 + 90 * 0.3 + (20/60/3*100) * 0.1
        assert score == pytest.approx(expected, rel=0.1)

    def test_incomplete(self):
        """未完成：15 字，1 错误，60 秒，20 总"""
        result = MatchResult(completed=15, total=20, errors=1, elapsed=60.0)
        score = result.score()
        
        # 完成率 75%, 正确率 93.3%, 速度 8.3
        expected = 75 * 0.6 + (14/15*100) * 0.3 + (15/60/3*100) * 0.1
        assert score == pytest.approx(expected, rel=0.1)

    def test_to_dict(self):
        """测试 to_dict 方法"""
        result = MatchResult(completed=18, total=20, errors=2, elapsed=60.0)
        data = result.to_dict()
        
        assert data["completed"] == 18
        assert data["total"] == 20
        assert data["errors"] == 2
        assert "score" in data
        assert "accuracy" in data
```

#### 协议测试示例

```python
# tests/unit/test_protocol.py

import pytest
from common.protocol import encode, decode, require

class TestProtocol:
    """协议层测试"""

    def test_encode_join(self):
        """测试编码 join 消息"""
        from common.protocol import c_join
        msg = c_join("张三")
        decoded = decode(msg)
        
        assert decoded["type"] == "join"
        assert decoded["name"] == "张三"

    def test_decode_invalid_json(self):
        """测试无效 JSON 处理"""
        assert decode("not json") is None
        assert decode(b"\x00\x01\x02") is None

    def test_require_fields(self):
        """测试字段验证"""
        valid_msg = {"type": "join", "name": "张三"}
        invalid_msg = {"type": "join"}
        
        assert require(valid_msg, "type", "name") == True
        assert require(invalid_msg, "type", "name") == False
        assert require(None, "type") == False
```

### 测试覆盖目标

| 模块 | 目标覆盖率 |
|------|-----------|
| common/protocol.py | 90%+ |
| common/models.py | 90%+ |
| server/game/ | 80%+ |
| client/ | 70%+ |

---

## 📚 文档贡献

### 文档类型

| 文档 | 位置 | 说明 |
|------|------|------|
| SPEC.md | 根目录 | 需求规格说明书 |
| ARCHITECTURE.md | 根目录 | 架构设计文档 |
| CHANGELOG.md | 根目录 | 版本变更日志 |
| ROADMAP.md | 根目录 | 产品路线图 |
| protocol.md | server/ | 通信协议详解 |
| 打包说明.md | 根目录 | 打包部署指南 |

### 文档更新要求

- 新增功能必须更新 SPEC.md
- 架构变更必须更新 ARCHITECTURE.md
- 版本发布必须更新 CHANGELOG.md
- 破坏性变更必须提前通知

### 文档风格

- 使用中文编写
- 使用 Markdown 格式
- 保持简洁清晰
- 提供代码示例

---

## 🐛 问题反馈

### 提交 Bug 报告

请使用 Issue 模板，包含以下信息：

```markdown
## Bug 描述
<!-- 清晰描述问题 -->

## 复现步骤
1. 
2. 
3. 

## 预期行为
<!-- 描述应该发生什么 -->

## 实际行为
<!-- 描述实际发生什么 -->

## 环境信息
- 操作系统: Windows XX
- Python 版本: X.X
- 项目版本: X.X.X

## 截图/日志
<!-- 如果有，添加截图或相关日志 -->
```

### 请求新功能

```markdown
## 功能描述
<!-- 详细描述您希望添加的功能 -->

## 使用场景
<!-- 这个功能解决什么问题？ -->

## 建议的实现方案
<!-- 如果有，描述您建议的实现方式 -->

## 替代方案
<!-- 其他可能的解决方案 -->
```

---

## 📞 联系方式

- **项目主页**: [GitHub Repository]
- **问题反馈**: [Issues]
- **讨论区**: [Discussions]

---

## 📄 许可证

TypeBattle 项目使用 [MIT 许可证](LICENSE)。

通过贡献代码，您同意您的代码将按照 MIT 许可证的条款发布。

---

*感谢您的贡献！*
