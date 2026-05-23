# 🎮 YDZ - 打字对战

> 局域网多人实时打字对战游戏

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.x-purple.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 目录

- [项目简介](#项目简介)
- [功能特点](#功能特点)
- [快速开始](#快速开始)
- [游戏规则](#游戏规则)
- [项目结构](#项目结构)
- [技术文档](#技术文档)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)

---

## 🎯 项目简介

YDZ 是一款局域网多人打字对战游戏，支持 2-32 名玩家同时在线进行淘汰赛制比赛。游戏采用客户端-服务端架构，通过 WebSocket 实现实时通信。

### 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| GUI | PyQt6 |
| 网络 | websockets |
| 打包 | PyInstaller |

---

## ✨ 功能特点

```
┌─────────────────────────────────────────────────────────────┐
│                      YDZ 功能                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🎯 核心功能                                                  │
│  ├── ✅ UDP 自动发现服务器                                    │
│  ├── ✅ 手动 IP 连接                                          │
│  ├── ✅ 最多 32 人同时在线                                     │
│  ├── ✅ 淘汰赛制（8强→4强→半决赛→决赛）                        │
│  ├── ✅ 轮空处理（奇数玩家）                                   │
│  ├── ✅ 实时逐字校验                                          │
│  ├── ✅ 服务端权威时间同步                                     │
│  ├── ✅ 暂停/恢复比赛                                          │
│  ├── ✅ 断线重连（10秒内）                                     │
│  └── ✅ 完整计分系统                                          │
│                                                              │
│  🎨 UI/UX                                                    │
│  ├── ✅ 登录页/大厅页/比赛页/结果页                            │
│  ├── ✅ 暂停/断线遮罩层                                        │
│  ├── ✅ F11 全屏模式                                          │
│  └── ✅ 字体自适应                                            │
│                                                              │
│  🛠️ 运维支持                                                  │
│  ├── ✅ 崩溃日志记录                                          │
│  ├── ✅ 网络诊断工具                                          │
│  └── ✅ 防火墙配置脚本                                        │
│                                                              │
│  🚧 开发中                                                   │
│  ├── 🔄 代码重构（v1.1）                                     │
│  ├── 📋 单元测试框架                                          │
│  ├── 🤖 AI 对战                                              │
│  └── 👁️ 观战模式                                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- Windows 10/11
- Python 3.9+

### 安装依赖

```bash
# 克隆项目
cd D:\type_battle

# 安装依赖
pip install pyqt6 websockets psutil
```

### 启动服务器

```bash
cd server
python main.py
```

服务器启动后，窗口会显示局域网 IP 地址：

```
╔════════════════════════════════════╗
║     YDZ 服务器已启动          ║
╠════════════════════════════════════╣
║  WebSocket: ws://192.168.1.100:8888 ║
║  UDP 发现端口: 23333                ║
╚════════════════════════════════════╝
```

### 启动客户端

```bash
cd client
python main.py
```

### 连接方式

#### 方式一：自动发现（推荐）

客户端启动后会自动搜索局域网内的服务器，找到后点击"加入"即可。

#### 方式二：手动输入 IP

1. 点击客户端下方的"▼ 手动输入IP"
2. 输入服务器显示的 IP 地址（如 `192.168.1.100`）
3. 输入您的昵称
4. 点击"加入"

---

## 📋 游戏规则

### 比赛流程

```
加入房间 → 等待准备 → 管理员开始 → 5秒倒计时 → 打字对战 → 轮次结算 → 决赛
```

### 计分公式

```
总得分 = 完成率 × 60% + 正确率 × 30% + 速度得分 × 10%

其中：
- 完成率 = (已打字数 / 总字数) × 100
- 正确率 = ((已打字数 - 错误数) / 已打字数) × 100
- 速度得分 = min(100, (已打字数 / 用时) / 3.0 × 100)
```

### 胜负判定

比赛结束后，系统根据综合得分决定胜负。得分高者晋级。

### 管理员权限

- 第一个加入房间的玩家自动成为管理员
- 管理员可以：开始比赛、暂停比赛、恢复比赛、强制结束比赛

---

## 📁 项目结构

```
D:\type_battle\
├── client/                      # 客户端
│   ├── main.py                  # 入口文件
│   ├── network.py               # WebSocket 客户端
│   ├── widgets.py               # UI 组件
│   └── pages/                   # 页面模块
│       ├── login.py            # 登录页
│       ├── lobby.py            # 大厅页
│       ├── battle.py           # 比赛页
│       ├── result.py           # 结果页
│       └── overlay.py          # 遮罩层
│
├── server/                      # 服务端
│   ├── main.py                 # 入口文件（待重构）
│   ├── protocol.md             # 通信协议文档
│   └── data/                   # 游戏数据
│
├── common/                      # 共享模块
│   ├── protocol.py             # 消息协议
│   ├── models.py              # 数据模型
│   └── logger.py              # 日志
│
├── docs/                        # 文档目录
│   ├── SPEC.md                # 需求规格说明书
│   ├── ARCHITECTURE.md        # 架构设计文档
│   ├── ROADMAP.md            # 产品路线图
│   └── REFACTORING.md        # 重构规划
│
├── CHANGELOG.md                # 更新日志
├── CONTRIBUTING.md             # 贡献指南
├── README.md                   # 本文档
└── 打包说明.md                  # 打包指南
```

---

## 📚 技术文档

| 文档 | 说明 |
|------|------|
| [SPEC.md](SPEC.md) | 需求规格说明书 - 功能需求和验收标准 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构设计文档 - 系统架构和模块设计 |
| [protocol.md](server/protocol.md) | 通信协议 - WebSocket 消息格式 |
| [ROADMAP.md](ROADMAP.md) | 产品路线图 - 版本规划和里程碑 |
| [REFACTORING.md](REFACTORING.md) | 重构规划 - 代码优化计划 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 - 如何参与开发 |
| [CHANGELOG.md](CHANGELOG.md) | 更新日志 - 版本变更记录 |

---

## ❓ 常见问题

### Q: 为什么连接不上服务器？

**A:** 请按以下步骤排查：

1. 确认服务器已启动并显示 IP 地址
2. 确认客户端和服务器在同一局域网内
3. 尝试使用手动输入 IP 方式连接
4. 运行 `server/add_firewall_rule.bat` 添加防火墙规则

详细解决方案请参考：[局域网连接问题解决指南](局域网连接问题解决指南.md)

### Q: 如何自定义打字文本？

**A:** 编辑 `server/data/texts.json` 文件，添加自定义文本。

### Q: 支持多少人同时在线？

**A:** 最多支持 32 名玩家同时在线。

### Q: 如何打包成 exe 文件？

**A:** 请参考 [打包说明.md](打包说明.md)

---

## 🤝 贡献指南

欢迎参与 YDZ 的开发！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何贡献代码。

### 当前版本路线图

```
v1.0 (当前) → v1.1 (代码重构) → v1.2 (质量提升) → v2.0 (AI对战)
```

详细计划请参考 [ROADMAP.md](ROADMAP.md)

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 开发者

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/cgop12">
        <img src="https://avatars.githubusercontent.com/u/266697329?v=4" width="80" height="80" alt="守望"><br>
        <strong>守望</strong>
      </a><br>
      <sub>发起人 & 测试</sub>
    </td>
    <td align="center">
      <a href="https://github.com/cgop12">
        <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f609.png" width="80" height="80" alt="小望"><br>
        <strong>小望</strong>
      </a><br>
      <sub>全栈架构 & 开发</sub>
    </td>
  </tr>
</table>

感谢所有参与项目开发的贡献者！

---

<p align="center">
  <strong>YDZ</strong> - 让打字变得有趣！
</p>
## 打包说明

客户端打包：
```
cd D:\YDZ\client
py -m PyInstaller YDZClient.spec --noconfirm
```

服务器端打包：
```
cd D:\YDZ\server
py -m PyInstaller YDZServer.spec --noconfirm
```

全部打包：
```
D:\YDZ\build_all.bat
```
