<h1 align="center">Hermes Telegram Downloader</h1>

<p align="center">
<strong>Telegram 媒体下载 / 转发 / 监听工具，带任务持久化 + 崩溃恢复 + 现代 WebUI</strong>
</p>

<p align="center">
<a href="https://github.com/MangoIsIllegal/hermes-telegram-downloader/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
<a href="https://github.com/MangoIsIllegal/hermes-telegram-downloader/releases"><img alt="Version" src="https://img.shields.io/badge/version-1.0.0-blue"></a>
<a href="https://www.python.org/downloads/"><img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue"></a>
<a href="https://hub.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/docker-ready-blue"></a>
</p>

<p align="center">
  <a href="#功能特性">功能特性</a> ·
  <a href="#架构设计">架构设计</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#配置说明">配置说明</a> ·
  <a href="#bot-命令">Bot 命令</a> ·
  <a href="#web-api">Web API</a> ·
  <a href="#相比上游的改动">相比上游的改动</a>
</p>

---

## 功能特性

### 下载

- **多类型媒体下载** — audio / document / photo / video / voice / animation / video_note
- **批量下载** — 指定消息 ID 范围 `[start, end]`，支持过滤器
- **单条下载** — 直接发送 `t.me` 链接给 Bot 即可下载
- **转发媒体下载** — 转发一条媒体消息给 Bot，自动从源频道下载
- **断点续传** — 文件大小 ≥ 已下载大小即判定为已完成，跳过重复下载
- **大小不匹配重下** — 已有文件但大小不符时，备份原文件后重新下载
- **3 次重试** — 每个文件最多重试 3 次，含指数退避（连接错误 10s/20s/40s）
- **文件引用过期处理** — BadRequest 时自动 fetch_message 刷新引用
- **临时文件清理** — 下载失败自动清理 `.temp` 文件，启动时清理残留

### 转发

- **跨频道转发** — 支持普通频道和受保护频道（has_protected_content）
- **受保护频道** — 自动切换为下载再上传模式
- **评论区转发** — `/forward_to_comments` 转发媒体到指定帖子评论区
- **实时监听转发** — `/listen_forward` 基于 NewMessage 事件驱动，频道有新消息立即触发下载/转发（非轮询）
- **config.yaml 频道监控** — 配置文件中的 chat 列表也会自动监听新消息，启动后实时更新

### 广告过滤

- **关键词过滤** — `/add_ad` 添加广告关键词，转发时自动跳过包含这些关键词的消息
- **关键词移除** — `/remove_ad` 移除广告关键词
- **内容替换** — `/add_replace_ad` 添加替换规则，自动从 caption 中删除匹配的广告文字
- **替换移除** — `/remove_replace_ad` 移除替换规则
- **群组广告** — `/set_ad` 为特定群组设置追加广告文字，转发时自动添加到 caption 末尾

### 任务管理

- **任务持久化** — 所有下载/转发任务写入 `log/bot_tasks.json`，容器重启不丢任务
- **崩溃恢复** — 重启后所有未完成任务统一进入 pending 队列，逐个消费
- **任务 ID** — `MMDD-序号` 格式（如 `0628-1`），每日序号重置，持久化计数器
- **Pending 队列** — 任务先入 pending 状态，由消费循环逐个喂给 worker 池；queued 状态区分已入队等待 worker 的任务
- **下载进度持久化** — 每 50 条消息自动保存 `last_read_message_id`，中断不丢进度
- **下载历史持久化** — 完成/失败记录写入 `log/download_history.json`
- **手动终止** — 停止任务时未完成文件记入失败列表（原因：手动终止）

### FLOOD_WAIT 处理

- **非阻塞式等待** — 设置冷却时间戳，不 sleep，不卡死整个队列
- **Pending 消费者限速** — get_messages 遇到 FloodWait 时全局冷却，任务保持 pending
- **下载限速** — 累计 FloodWait > 600 秒则跳过该文件
- **消息编辑限速** — edit_message 遇到 FloodWait 时设置 node 级冷却
- **用户通知** — 限速暂停时发送 Telegram 通知告知用户
- **静默限速检测** — 检测 TG 静默限速（速度 < 200 KB/s 持续 120 秒），无 FloodWait 错误码也能识别，WebUI 横幅显示已限速时长 + TG 通知（触发和解除各一次）

### WebUI

- **现代浅色主题** — 移除 layui，纯原生 HTML/CSS/JS，响应式设计
- **四个标签页**：
  - 📥 **进行中** — 活跃下载，实时进度/速度/ETA
  - ✅ **已完成** — 无限滚动，服务端搜索
  - ❌ **失败** — 失败原因 + 源消息链接，支持重试
  - ⏳ **待执行** — pending/queued 队列，等待时间显示，区分等待中/排队中状态
- **操作** — 暂停/恢复、删除（单个/批量）、重试（单个/批量）
- **实时数据** — 总速度 = 所有活跃任务速度之和，3 秒无回调判为过期归零
- **粘性导航栏** — 滚动时标签页固定在顶部

### 通知

- **进度通知** — 每 20% 进度里程碑发送一次 Bot 消息更新
- **完成通知** — 任务完成时立即发送最终状态（从 _download_result 重新计数，避免竞态）
- **失败通知** — 列出每个失败文件及具体错误原因
- **限速通知** — FLOOD_WAIT 暂停时通知用户等待时长
- **静默限速** — TG 静默限速检测（速度 < 200 KB/s 持续 120 秒），WebUI 横幅显示已限速时长 + TG 通知（触发和解除各一次）
- **恢复通知** — 重启后恢复中断/待执行任务时通知用户
- **重试通知** — WebUI 重试任务加入队列时通知用户

### 其他

- **多语言** — 中文 / 英文 / 俄语 / 乌克兰语
- **rclone 云盘上传** — 下载完成后可选上传到云盘
- **代理支持** — Pyrogram 原生代理 + Docker 环境变量代理
- **本地开发模式** — `run_local.py` 无需 Telegram 账号，Mock 数据调试 WebUI
- **日志分离** — `tdl.log`（主日志）+ `download.log`（下载日志），10MB 轮转，保留 30 天

---

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│                    Docker Container                  │
│                                                       │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ Bot (TG) │   │  WebUI :5000 │   │  Worker Pool │ │
│  │ Pyrogram │   │   Flask      │   │  (N workers) │ │
│  └────┬─────┘   └──────┬───────┘   └──────┬───────┘ │
│       │                │                   │         │
│       │    ┌───────────┼───────────────────┘         │
│       │    │           │                             │
│       ▼    ▼           ▼                             │
│  ┌────────────────────────────┐                      │
│  │    asyncio.Queue           │                      │
│  │  (message, node) tuples    │                      │
│  └────────────┬───────────────┘                      │
│               │                                      │
│               ▼                                      │
│  ┌────────────────────────────┐                      │
│  │  Pending Consumer Loop     │                      │
│  │  (every 5s, fill workers)  │                      │
│  └────────────┬───────────────┘                      │
│               │                                      │
│               ▼                                      │
│  ┌────────────────────────────┐                      │
│  │  task_store.py             │                      │
│  │  log/bot_tasks.json        │                      │
│  │  log/task_counter.json     │                      │
│  └────────────────────────────┘                      │
│                                                       │
│  ┌────────────────────────────┐                      │
│  │  download_stat.py          │                      │
│  │  log/download_history.json │                      │
│  └────────────────────────────┘                      │
│                                                       │
│  ┌────────────────────────────┐                      │
│  │  Downloads / Sessions      │                      │
│  │  /app/downloads/           │                      │
│  │  /app/sessions/            │                      │
│  └────────────────────────────┘                      │
└─────────────────────────────────────────────────────┘
```

### 核心流程

1. **用户发命令** → Bot handler 创建 TaskNode → `save_task()` 持久化 → `add_download_task()` 入队
2. **Worker 从队列取任务** → `download_task()` → `download_media()` → Pyrogram 下载
3. **进度回调** → `update_download_status()` 更新 `_download_result` → 20% 里程碑触发 Bot 通知
4. **下载完成** → `complete_task()` 从持久化移除 → `save_downloads()` 写入历史
5. **下载失败** → `add_failed_download()` 记入失败列表 → WebUI 可重试
6. **容器重启** → `recover_tasks()` 读取未完成任务 → 全部重置为 pending → 消费循环逐个喂入 worker

### Pending 消费者机制

重启时所有未完成任务统一进入 pending 队列，而非直接恢复。这解决了旧版本重启时 100+ 任务同时恢复导致 FLOOD_WAIT 风暴的问题。

```
pending task → _consume_one_pending() → get_messages(300s timeout)
    ├─ 成功 → 创建 placeholder → add_download_task() → worker 下载
    ├─ FloodWait → 全局冷却 → 任务保持 pending → 通知用户
    ├─ 超时 → 记入失败列表 → 移除 pending
    └─ 其他异常 → 记入失败列表 → 移除 pending

_pending_consumer_loop() 每 5 秒：
    └─ 填充最多 max_download_task 个 pending 任务到 worker 队列
```

### TCP 超时补丁

Pyrogram 默认 `TCP.TIMEOUT=10s`，在 TG 限速时导致连接拆除 + MTProto 重新握手，产生大量上传流量。补丁改为 900 秒：

```python
from pyrogram.connection.transport.tcp import TCP as _TCP
_TCP.TIMEOUT = 900
```

---

## 快速开始

### Docker 部署（推荐）

```bash
git clone https://github.com/MangoIsIllegal/hermes-telegram-downloader.git
cd hermes-telegram-downloader

# 复制配置
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入 api_id / api_hash / bot_token

# 首次运行（前台，用于登录 Telegram）
docker-compose run --rm hermes-telegram-downloader

# 后续后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 手动安装

```bash
git clone https://github.com/MangoIsIllegal/hermes-telegram-downloader.git
cd hermes-telegram-downloader
pip install -r requirements.txt

cp config.yaml.example config.yaml
# 编辑 config.yaml...

python media_downloader.py
```

### 本地开发模式

```bash
# 无需 Telegram 账号，Mock 数据启动 WebUI
python run_local.py
# 访问 http://localhost:5000
```

---

## 配置说明

### config.yaml

```yaml
# Telegram API 凭证（必填）
api_id: your_api_id
api_hash: your_api_hash
bot_token: your_bot_token  # Bot Token，用于 Bot 命令交互

# 媒体类型
media_types:
  - audio
  - document
  - photo
  - video
  - voice
  - animation

# 文件格式过滤（all = 所有格式）
file_formats:
  audio:
    - all
  document:
    - pdf
    - epub
  video:
    - mp4

# 下载设置
save_path: /app/downloads
file_path_prefix:
  - chat_title
  - media_datetime
file_name_prefix:
  - file_name
hide_file_name: false

# 并发控制
max_download_task: 5  # worker 数量

# WebUI
web_host: 0.0.0.0
web_port: 5000
web_login_secret: 123  # 登录密钥；非空则所有页面和 API 都要登录，留空则不启用。请改掉示例值

# 权限
allowed_user_ids:
  - 'me'  # 'me' = 当前登录账号

# 其他
language: ZH
date_format: '%Y_%m'
enable_download_txt: false
log_level: DEBUG

# 代理（Docker 内访问宿主机代理）
proxy:
  scheme: http
  hostname: 172.17.0.1
  port: 20172
```

### 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `api_id` | Telegram API ID（[my.telegram.org](https://my.telegram.org/apps)） | — |
| `api_hash` | Telegram API Hash | — |
| `bot_token` | Bot Token（[@BotFather](https://t.me/BotFather)） | — |
| `media_types` | 下载的媒体类型列表 | — |
| `file_formats` | 各类型文件格式过滤 | — |
| `save_path` | 文件保存路径 | `./downloads` |
| `max_download_task` | 并发下载 worker 数 | `5` |
| `web_port` | WebUI 端口 | `5000` |
| `allowed_user_ids` | 允许使用 Bot 的用户 ID（`'me'` = 自己） | `[]` |
| `language` | 界面语言（`ZH` / `EN` / `RU` / `UA`） | `EN` |
| `proxy` | 代理配置（scheme / hostname / port） | `{}` |
| `log_level` | 日志级别 | `INFO` |
| `hide_file_name` | 隐藏文件名（UI 显示 `****.mp4`） | `false` |
| `enable_download_txt` | 纯文本消息保存为 .txt | `false` |
| `date_format` | 日期目录格式 | `%Y_%m` |

---

## Bot 命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/download <link> <start> <end> [filter]` | 批量下载消息 | `/download https://t.me/c/123 1 100` |
| `/forward <src> <dst> <start> <end> [filter]` | 转发消息到目标群组 | `/forward https://t.me/c/A https://t.me/c/B 1 500` |
| `/forward_to_comments <src> <dst> <start> <end>` | 转发媒体到评论区 | `/forward_to_comments https://t.me/c/A https://t.me/c/B 1 10` |
| `/listen_forward <src> <dst> [filter]` | 实时监听并自动转发 | `/listen_forward https://t.me/c/A https://t.me/c/B` |
| `/get_info <link>` | 获取群组/频道/消息信息 | `/get_info https://t.me/c/123/456` |
| `/add_filter <filter>` | 设置下载过滤器 | `/add_filter message_date >= 2024-01-01` |
| `/add_ad <keyword>` | 添加广告关键词（转发时跳过） | `/add_ad 推广` |
| `/remove_ad <keyword>` | 移除广告关键词 | `/remove_ad 推广` |
| `/add_replace_ad <msg_link> <keyword>` | 添加替换规则（从 caption 删除） | `/add_replace_ad https://t.me/c/123/456 广告` |
| `/remove_replace_ad <msg_link> <keyword>` | 移除替换规则 | `/remove_replace_ad https://t.me/c/123/456 广告` |
| `/set_ad <msg_link> <ad_text>` | 设置群组追加广告（空文本删除） | `/set_ad https://t.me/c/123 关注我` |
| `/set_language <lang>` | 设置语言（en/ru/zh/ua） | `/set_language zh` |
| `/stop` | 停止下载/转发/监听（交互式按钮） | `/stop` |
| `/help` `/start` | 显示帮助 | — |

### 快捷操作（无需命令）

- **发送 `t.me` 链接** → 下载单条消息
- **转发媒体消息给 Bot** → 下载该媒体（优先从源频道下载）

### 消息 ID 说明

- `start_id = 1` → 从最早的消息开始
- `end_id = 0` → 直到最新消息
- `[filter]` 可选，支持日期/文件名等过滤

---

## Web API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | WebUI 主页 |
| `/get_download_list` | GET | 下载列表（`already_down=true` 已完成，`false` 进行中） |
| `/get_download_list?offset=0&limit=50&search=keyword` | GET | 已完成列表（分页 + 搜索） |
| `/get_pending_list` | GET | Pending 队列 |
| `/get_failed_downloads` | GET | 失败列表 |
| `/get_download_status` | GET | 总下载速度 |
| `/get_download_state` | GET | 全局下载状态（downloading / paused） |
| `/get_completed_count` | GET | 已完成数量（轻量轮询） |
| `/get_flood_wait` | GET | FloodWait 冷却状态 + 剩余秒数 |
| `/get_app_version` | GET | 应用版本 |
| `/check_file_exists` | POST | 检查已完成任务的本地文件是否存在 |
| `/set_download_state` | POST | 全局暂停/恢复（`state=pause` / `state=continue`） |
| `/pause_task` | POST | 暂停单个任务 |
| `/resume_task` | POST | 恢复单个任务 |
| `/delete_task` | POST | 删除任务（活跃或失败） |
| `/batch_delete` | POST | 批量删除（JSON: `{"task_ids": [...]}`） |
| `/retry_task` | POST | 重试失败任务 |
| `/batch_retry` | POST | 批量重试（JSON: `{"task_ids": [...]}`） |
| `/remove_pending` | POST | 移除 pending 任务 |

---

## Docker 管理

```bash
# 构建镜像
docker-compose build

# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down

# 重启
docker-compose restart

# 更新代码后重新构建
git pull && docker-compose build && docker-compose up -d
```

### 数据持久化

| 路径 | 说明 |
|------|------|
| `./downloads/` | 下载的文件 |
| `./config.yaml` | 配置文件 |
| `./data.yaml` | 运行时数据（ids_to_retry 等） |
| `./log/` | 日志 + 任务持久化（bot_tasks.json / task_counter.json / download_history.json） |
| `./sessions/` | Telegram session 文件 |
| `./temp/` | 下载临时文件 |

---

## 相比上游的改动

基于 [tangyoha/telegram_media_downloader](https://github.com/tangyoha/telegram_media_downloader) v2.2.6 深度改造。

### 新增模块

| 模块 | 说明 |
|------|------|
| `module/task_store.py` | 任务持久化 + 崩溃恢复，JSON 存储，原子写入，线程安全 |
| `run_local.py` | 本地开发模式，Mock 数据，无需 Telegram |

### 核心改动

| 改动 | 上游 | 本项目 |
|------|------|--------|
| **任务持久化** | 无（重启丢任务） | `bot_tasks.json` + `task_counter.json`，崩溃后自动恢复 |
| **下载历史** | 无 | `download_history.json`，完成/失败记录持久化 |
| **任务 ID** | 纯递增整数 | `MMDD-序号` 格式，每日重置，持久化计数器 |
| **Web UI** | layui 框架 | 纯原生 HTML/CSS/JS，浅色主题，响应式 |
| **WebUI 功能** | 基础列表 | 4 标签页 + 暂停/恢复 + 删除 + 重试 + 搜索 + 无限滚动 |
| **Pending 队列** | 无 | 重启任务统一入 pending，逐个消费，防 FLOOD_WAIT 风暴 |
| **FLOOD_WAIT** | 阻塞 sleep | 非阻塞冷却时间戳，不卡死队列 |
| **静默限速** | 不检测 | 速度 < 200 KB/s 持续 120 秒 → WebUI 横幅 + TG 通知（触发和解除各一次） |
| **并发任务数** | 固定（config） | WebUI 下拉框动态调整 1-6，实时生效 |
| **进度通知** | 定时轮询 | 20% 里程碑触发 + 完成立即通知 + 从 _download_result 重计数 |
| **失败处理** | 仅日志 | 失败列表持久化 + 错误原因 + 源链接 + WebUI 重试 |
| **停止任务** | 直接停止 | 未完成文件记入失败列表（手动终止），不留残留 |
| **TCP 超时** | 10s（默认） | 900s，防止限速时 reconnect 风暴 |
| **下载重试** | 3 次 5s 间隔 | 3 次，OSError 指数退避（10s/20s/40s） |
| **大小不匹配** | 直接覆盖 | 备份 .bak 后重下，成功删备份 |
| **文件引用过期** | 日志记录 | 自动 fetch_message 刷新引用 |
| **Queue 初始化** | 模块导入时 | 事件循环启动后，避免 loop 不匹配 |
| **日志** | 单文件 | `tdl.log` + `download.log`，10MB 轮转，30 天保留 |
| **Bot 通知** | 简单状态 | 下载进度 + 完成文件列表 + 失败原因 + 限速暂停 + 恢复通知 |
| **Docker** | 单阶段 | 多阶段构建（alpine），rclone 内置 |
| **版本号** | v2.2.6 | v1.0.0（独立版本线） |

---

## License

[MIT](./LICENSE)

## 致谢

- 原项目：[tangyoha/telegram_media_downloader](https://github.com/tangyoha/telegram_media_downloader)
- Pyrogram：[pyrogram](https://github.com/pyrogram/pyrogram)
