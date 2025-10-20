# Twitter 自动回复微服务

本仓库收集了一组用于自动化 Twitter（X）互动的微服务。目前的核心服务 `post` 会根据搜索条件监控推文，并按热度排序（基于互动指标）后生成符合品牌调性的回复。

## 功能亮点
- 完整接入 OAuth 2.0 用户上下文授权流程，并自动刷新 token。
- Twitter 最近搜索结果请求 `public_metrics` 后，依据点赞、转推、回复、引用等互动指标计算热度得分，让机器人优先处理热门内容。
- OpenAI 负责回复生成与分类，可通过 `--dry-run` 模式仅记录而不发送。
- 持久化保存处理过的推文与 OAuth 状态，避免重复回复并且可随时恢复运行。
- 提供 Typer CLI 与 Docker 方案，方便本地或容器化部署。

## 目录结构
- `app/post/` – 推特自动回复 Python 微服务。
  - `src/` – 业务代码（`bot.py`、`twitter_service.py` 等）。
  - `requirements.txt` – 依赖清单。
  - `Dockerfile` – 容器镜像定义。
  - `var/` – 运行期存储（`state.json`、`token_state.json`）。
- `app/backend/` – 预留的后端服务目录。
- `app/frontend/` – 预留的前端项目目录。

## 快速开始（post 服务）
1. 进入服务目录：
   ```bash
   cd app/post
   ```
2. 创建并激活 Python 3.11+ 虚拟环境。
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
4. 复制 `.env.example`（如存在）为 `.env`，并填写必要变量：
   - `TWITTER_CLIENT_ID`, `TWITTER_CLIENT_SECRET`
   - `TWITTER_ACCESS_TOKEN`, `TWITTER_REFRESH_TOKEN`
   - `TWITTER_REDIRECT_URI`
   - `TWITTER_SEARCH_QUERY`
   - `OPENAI_API_KEY`（可选；未提供时仅记录，不会发表回复）

### 热度相关配置
- 代码会基于点赞、转推、回复、引用等数据计算热度得分，并按分值（其次是 tweet ID）降序处理。
- `STATE_PATH` / `TOKEN_STORE_PATH`：覆盖默认状态文件位置（默认保存在 `app/post/var`）。
- 其他常用参数：`POLL_INTERVAL_SECONDS`、`MAX_TWEETS_PER_RUN`、`TWITTER_SCOPES`、`TWITTER_BOT_USERNAME`。

## 授权辅助命令
在 `app/post` 下使用 Typer CLI 完成 OAuth 2.0 PKCE 流程：
```bash
python -m src.main auth walkthrough
```
常用子命令：
- `python -m src.main auth link` – 输出授权链接与 PKCE 参数。
- `python -m src.main auth exchange --code <code> --code-verifier <verifier>` – 手动兑换授权码。

Token 会保存到 `var/token_state.json`，如果 `.env` 存在也会同步写入。

## 运行机器人
```bash
python -m src.main run --log-level INFO
```
如需仅观察生成结果但不真正发送回复，可加 `--dry-run`。

### Docker / Compose
```bash
docker compose up --build post
```
Compose 会把 `./app/post/var` 挂载进容器，保证状态持久化。

## 测试建议
- 将 `TWITTER_SEARCH_QUERY` 指向测试账号或标签，在 `--dry-run` 下观察回复质量。
- 单元测试时可为 `TwitterClient`、`ReplyGenerator` 注入 mock。
- 待后端/前端服务成型后，再补充端到端或冒烟测试。

## 路线图
- 在 `app/backend` 中构建 API 编排与分析服务。
- 搭建 `app/frontend` 仪表盘，实时监控互动情况。
- 探索热度得分的动态权重或时间衰减模型，进一步提升“热门”判断准确度。
