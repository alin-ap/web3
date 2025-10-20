# Repository Guidelines

## 项目结构与模块组织
- `app/post/src/` 是推特自动回复服务核心：`main.py` 提供 Typer CLI，`bot.py` 负责轮询与回复调度，`twitter_service.py` 封装 API 调用，`openai_service.py` 管理 LLM 交互，`storage.py` 负责状态持久化。
- 运行态数据保存在 `app/post/var/`（如 `state.json`、`token_state.json`）；`docker-compose.yml` 会把该目录挂载进容器，方便本地调试与生产共享。
- `.env` 位于仓库根目录，供 Compose 和 CLI 读取；新增环境变量时记得更新示例文件并在指南中说明用途。
- `app/backend/`、`app/frontend/` 目前为空壳，后续服务建议沿用 `src/` + `tests/` + `README.md` 的布局，保持文档同步。

## 构建、测试与开发命令
- `cd app/post && pip install -r requirements.txt` 安装 Python 3.11 依赖，推荐使用 `python -m venv .venv && source .venv/bin/activate` 创建虚拟环境。
- `python -m src.main run --dry-run` 启动机器人但仅记录生成结果；去掉 `--dry-run` 即可实际发文，常用于回归验证。
- `python -m src.main auth link` 生成 OAuth 链接与 PKCE 参数，随后执行 `python -m src.main auth exchange --code <code> --code-verifier <verifier>` 写入 token；若需要引导流程，可使用 `python -m src.main auth walkthrough`。

## 代码风格与命名约定
- 统一使用四空格缩进、PEP 484 类型标注与文件级 docstring；函数与变量保持 `snake_case`，类及数据类采用 `PascalCase`。
- 日志全部走 `logging`，遵循 `configure_logging` 定义的格式和等级；CLI 参数通过 Typer 声明并加上精准帮助信息。
- 变量能写死的尽量直接写死
- 保持代码的简洁和易读性非常重要

## 提交与 PR 指南
- 延续 `<type>: 摘要` 的格式（英文类型 + 精简中文描述），使用 ASCII 冒号并控制在 60 字以内，如 `feature: 调整轮询间隔策略`。
- 合并前整理 commit，必要时进行 squash；若关联 Issue 或任务单，在正文或 PR 描述中显式引用。
- PR 需概述变更影响、列出新增环境变量或迁移步骤，并附相关截图/日志；提交前确认测试、lint 状态并写入清单。

## 安全与配置提示
- 机密信息仅放入 `.env` 或个人覆写文件，禁止提交 `app/post/var` 内的 token 缓存；敏感部署可改用 Docker secrets 或 CI 密钥库。
- 轮换授权或密钥后务必清理 `var/token_state.json` 并重启服务，保证全新 OAuth 握手流程。
