# Twitter 自动回复微服务

本仓库收集了一组用于自动化 Twitter（X）互动的微服务。目前的核心服务 `post` 会根据搜索条件监控推文，并按热度排序（基于互动指标）后生成符合品牌调性的回复。

## 功能亮点
- 完整接入 OAuth 2.0 用户上下文授权流程，并自动刷新 token。
- Twitter 最近搜索结果请求 `public_metrics` 后，依据点赞、转推、回复、引用等互动指标计算热度得分，让机器人优先处理热门内容。
- OpenRouter（OpenAI 兼容接口）负责回复生成与分类，可通过 `--dry-run` 模式仅记录而不发送。

## 目录结构
- `app/post/` – 推特自动回复 Python 微服务。
  - `src/` – 业务代码（`bot.py`、`twitter_service.py` 等）。
  - `requirements.txt` – 依赖清单。
  - `Dockerfile` – 容器镜像定义。
  - `var/` – 运行期存储（`state.json`、`token_state.json`）。
- `app/backend/` – 预留的后端服务目录。
- `app/frontend/` – 预留的前端项目目录。

## 运行机器人
```bash
python -m src.main run --log-level INFO
```
如需仅观察生成结果但不真正发送回复，可加 `--dry-run`。

## 环境变量
- `OPENROUTER_API_KEY`：从 OpenRouter 控制台获取，用于调用统一的 LLM 接口。


## 模型配置
- 默认回复模型为 `google/gemini-1.5-pro-latest`，分类模型为 `google/gemini-1.5-flash-latest`；如需调整可在 `app/post/config.yml` 的 `models` 段替换为 OpenRouter 支持的其他模型。


## 同时运行两个：
同时运行多个账号时，在不同终端设置 TWITTER_HANDLE 启动：

TWITTER_HANDLE=punkstrategys python -m src.main run
TWITTER_HANDLE=EveZero_42 python -m src.main run

## 授权：
python -m src.main auth walkthrough --handle punkstrategys
python -m src.main auth walkthrough --handle EveZero_42
