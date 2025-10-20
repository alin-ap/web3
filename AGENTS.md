# Repository Guidelines

## 项目结构与模块组织
- `app/post/src/` 是推特自动回复服务核心：`main.py` 提供 Typer CLI，`bot.py` 负责轮询与回复调度，`twitter_service.py` 封装 API 调用，`openai_service.py` 管理 LLM 交互，`storage.py` 负责状态持久化。
- 运行态数据保存在 `app/post/var/`（如 `state.json`、`token_state.json`）；`docker-compose.yml` 会把该目录挂载进容器，方便本地调试与生产共享。
- `.env` 位于仓库根目录，供 Compose 和 CLI 读取；新增环境变量时记得更新示例文件并在指南中说明用途。
- `app/post/prompts/` 存放按 persona 拆分的回复/分类 prompt，路径由 `config.yml` 的 `personas` 段引用。
- 账号排除名单、persona、token 等均在 `app/post/config.yml` 中维护；`bots.ignore_handles` 控制哪些用户名不会被自动回复。
- OAuth 刷新令牌按账号写入 `app/post/var/token_<handle>.json`，记得随部署携带。
- `app/backend/`、`app/frontend/` 目前为空壳，后续服务建议沿用 `src/` + `tests/` + `README.md` 的布局，保持文档同步。

## 构建、测试与开发命令
- `cd app/post && pip install -r requirements.txt` 安装 Python 3.11 依赖，推荐使用 `python -m venv .venv && source .venv/bin/activate` 创建虚拟环境。
- `python -m src.main run --dry-run` 启动机器人但仅记录生成结果；去掉 `--dry-run` 即可实际发文，常用于回归验证。
- `python -m src.main auth link` 生成 OAuth 链接与 PKCE 参数，随后执行 `python -m src.main auth exchange --code <code> --code-verifier <verifier>` 写入 token；若需要引导流程，可使用 `python -m src.main auth walkthrough`。

## 代码风格与命名约定
- 统一使用四空格缩进、PEP 484 类型标注与文件级 docstring；函数与变量保持 `snake_case`，类及数据类采用 `PascalCase`。
- 日志全部走 `logging`，遵循 `configure_logging` 定义的格式和等级；CLI 参数通过 Typer 声明并加上精准帮助信息。
- 优先保持代码简洁直接：变量能写死就写死；当输入约定明确时，不做额外的“防御式”处理，宁可在异常路径上抛出错误。
- 所有新特性都应让“失败优先”地暴露配置问题，便于快速定位。

## 提交与 PR 指南
- 延续 `<type>: 摘要` 的格式（英文类型 + 精简中文描述），使用 ASCII 冒号并控制在 60 字以内，如 `feature: 调整轮询间隔策略`。
- 提交信息遵循 `<type>[scope]: <description>` 模式，其中：
  - `type`（必填）：`feat` 新增功能、`fix` 修复 Bug、`refactor` 重构（不新增功能也不修复 Bug）、`style` 格式调整（不影响运行）、`test` 测试改动、`docs` 文档变更、`chore` 构建或工具更新。
  - `scope`（可选）：标记受影响的服务或模块。
  - `description`（必填）：一句话概括本次修改，不用句号。
- 合并前整理 commit，必要时进行 squash；若关联 Issue 或任务单，在正文或 PR 描述中显式引用。
- PR 需概述变更影响、列出新增环境变量或迁移步骤，并附相关截图/日志；提交前确认测试、lint 状态并写入清单。

## 安全与配置提示
- 机密信息仅放入 `.env` 或个人覆写文件
