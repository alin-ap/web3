"""Configuration helpers for the auto-reply bot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

import yaml
from dotenv import load_dotenv


load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yml"
DEFAULT_REPLY_PROMPT = ("""
## Persona
你是一位言辞犀利、观点鲜明的链上原生crypto玩家，也是PunkStrategy($PNKSTR)的支持者，也是PunkStrategyStrategy ($PSS)的项目方。你的人设是一个自信的市场老炮，早已厌倦了圈内的各种陈词滥调和虚假炒作。你的首要目标是挑起辩论，引发争议，并让人们觉得“这家伙肯定知道些我不知道的内幕”。

## Objective
你的任务是针对一条给定的推文撰写回复。你的回复必须通过一种强大到无法被忽视的声音，来最大化真实互动（回复、点赞）并吸引他人访问你的个人主页。

### Core Tactics
从以下的5个策略，选择 1-2 个策略去回复。
    1. 镜像与摧毁 (Mirror & Demolish): 引用一个关键短语，然后用一个尖锐、逆向的“真相”将其彻底击溃。
    2. 唯一重要的问题 (The Only Question That Matters): 提出一个强有力的问题，直击要害，揭示问题的本质。
    3. 残酷见解 (Brutal Insight): 给出一个别人不敢明说的、残酷而诚实的见解或法则。
    4. 伪二元对立 (False Dichotomy): 将辩论框定为一个非黑即白的“A vs B”选项，其中 A 是你推崇的机制，B 是一个明显有缺陷的替代品。
    5. 大胆断言 (Bold Proclamation): 针对某个机制或趋势，发表一个强硬的、近乎夸张的信念声明，并用纯粹的信念感为其背书。

## Brand Guidelines
我们的项目是 PunkStrategyStrategy ($PSS)，一个去中心化的、社区驱动的 DeFi 协议，旨在通过自动化流动性管理和代币回购来提升用户收益。PSS 通过其独特的代币经济模型，激励用户参与并持有 $PSS 代币，从而实现协议的可持续发展。
整个项目基于PunkStrategy($PNKSTR)去构建生态系统，所以务必要吹捧PNKSTR

PSS运作逻辑如下：
1 **交易税机制**：每笔 $PSS 交易征收 10% 税费，其中 2% 分配给开发团队，其余 8% 自动进入协议池。
2️**自动化执行**：当协议池累积足够手续费，任何用户均可调用合约执行“添加流动性”操作，将累积的 ETH 用于购买 $PNKSTR 并注入 LP。
3️ **流动性收益循环**：LP 产生的手续费由合约自动记录，任何人均可触发“回购与销毁”函数，将做市费用于回购 $PSS 并直接销毁。


## Strict Rules (绝对规则)
语言: 永远使用与原推文相同的语言。
语气: 避免无聊的喊单和空洞的炒作。语言风格一定要真实，像是一个有血有肉的人在说话，而不是一个营销机器人。
格式: 保持回复简练：1-2 句话是最佳状态。甚至可以就是一个单词，一个表情。
"""
)


DEFAULT_CLASSIFICATION_PROMPT = (
    "You triage tweets for the PunkStrategyStrategy ($PSS) outreach bot. Reply only when the tweet is genuinely "
    "about crypto, DeFi, market commentary, or an audience that might welcome an educational mention of PSS. "
    "Skip ads, giveaways, irrelevant chatter, personal complaints, or sensitive/regulatory news. Output 'SKIP' (uppercase) "
    "when the bot should stay silent. For any tweet that is acceptable to engage, respond with a short acknowledgment or "
    "summary (any text is fine, just not SKIP). "
)

VAR_DIR = CONFIG_PATH.parent / "var"


@dataclass(slots=True)
class DefaultsConfig:
    poll_interval_seconds: int = 300
    max_tweets_per_run: int = 10


@dataclass(slots=True)
class ModelsConfig:
    reply_model: str
    classifier_model: str


@dataclass(slots=True)
class AccountConfig:
    handle: str
    persona: Optional[str]
    access_token: str
    refresh_token: str
    search_query: str


@dataclass(slots=True)
class BotsConfig:
    defaults: DefaultsConfig
    models: ModelsConfig
    accounts: dict[str, AccountConfig]
    ignore_handles: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "BotsConfig":
        defaults_raw = raw.get("defaults")
        if defaults_raw is None:
            defaults = DefaultsConfig()
        elif isinstance(defaults_raw, dict):
            defaults = DefaultsConfig(
                poll_interval_seconds=int(defaults_raw.get("poll_interval_seconds", 300)),
                max_tweets_per_run=int(defaults_raw.get("max_tweets_per_run", 10)),
            )
        else:
            raise RuntimeError("config.yml 的 defaults 节必须是字典")

        models_raw = raw.get("models")
        if not isinstance(models_raw, dict):
            raise RuntimeError("config.yml 缺少 models 节配置")
        reply_model = str(models_raw.get("reply_model", "")).strip()
        classifier_model = str(models_raw.get("classifier_model", "")).strip()
        if not reply_model:
            raise RuntimeError("config.yml 缺少 models.reply_model 配置")
        if not classifier_model:
            raise RuntimeError("config.yml 缺少 models.classifier_model 配置")
        models = ModelsConfig(reply_model=reply_model, classifier_model=classifier_model)

        ignore_handles: tuple[str, ...] = ()
        bots_raw = raw.get("bots")
        if bots_raw is not None and not isinstance(bots_raw, dict):
            raise RuntimeError("config.yml 的 bots 节必须是字典")
        if isinstance(bots_raw, dict):
            handles = bots_raw.get("ignore_handles")
            if handles is None:
                ignore_handles = ()
            elif isinstance(handles, (list, tuple)):
                ignore_handles = tuple(
                    str(item).strip().lower().lstrip("@")
                    for item in handles
                    if str(item).strip()
                )
            else:
                raise RuntimeError("config.yml 的 bots.ignore_handles 必须是列表")

        groups_raw = raw.get("groups")
        if not isinstance(groups_raw, list) or not groups_raw:
            raise RuntimeError("config.yml 缺少 groups 节配置")

        accounts: dict[str, AccountConfig] = {}
        for group in groups_raw:
            if not isinstance(group, dict):
                raise RuntimeError("config.yml groups 成员必须是字典")
            persona_value = group.get("persona")
            persona = str(persona_value).strip() if persona_value else None
            accounts_raw = group.get("accounts")
            if not isinstance(accounts_raw, list) or not accounts_raw:
                raise RuntimeError("config.yml persona group 缺少 accounts 配置")
            for account_raw in accounts_raw:
                if not isinstance(account_raw, dict):
                    raise RuntimeError("config.yml account 项必须是字典")
                handle = str(account_raw.get("handle", "")).strip()
                if not handle:
                    raise RuntimeError("config.yml 发现缺少 handle 的账号配置")
                key = handle.lower().lstrip("@")
                if key in accounts:
                    raise RuntimeError(f"config.yml 中存在重复账号: {handle}")
                access_token = str(account_raw.get("access_token", "")).strip()
                refresh_token = str(account_raw.get("refresh_token", "")).strip()
                search_query = str(account_raw.get("search_query", "")).strip()
                if not access_token or not refresh_token:
                    raise RuntimeError(f"账号 {handle} 缺少 access_token 或 refresh_token")
                if not search_query:
                    raise RuntimeError(f"账号 {handle} 缺少 search_query")
                accounts[key] = AccountConfig(
                    handle=handle,
                    persona=persona,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    search_query=search_query,
                )

        if not accounts:
            raise RuntimeError("config.yml 中没有配置任何账号")

        return cls(
            defaults=defaults,
            models=models,
            accounts=accounts,
            ignore_handles=ignore_handles,
        )

    def select_account(self, handle_hint: Optional[str]) -> AccountConfig:
        if not self.accounts:
            raise RuntimeError("config.yml 中没有配置任何账号")
        if handle_hint:
            key = handle_hint.lower().lstrip("@")
            try:
                return self.accounts[key]
            except KeyError as exc:
                raise RuntimeError(f"config.yml 未找到 handle={handle_hint} 的账号配置") from exc
        return next(iter(self.accounts.values()))


def load_bots_config(path: Path) -> Optional[BotsConfig]:
    if not path.exists():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuntimeError(f"解析配置文件失败: {path}") from exc
    if raw is None:
        raise RuntimeError(f"{path} 是空文件")
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} 的顶层配置必须是字典")
    return BotsConfig.from_dict(raw)


BOTS_CONFIG = load_bots_config(CONFIG_PATH)


@dataclass(slots=True)
class OpenAISettings:
    model: str
    classifier_model: str
    api_key: Optional[str] = field(default=None, repr=False)
    reply_style_prompt: str = DEFAULT_REPLY_PROMPT
    classification_prompt: str = DEFAULT_CLASSIFICATION_PROMPT


def _select_account(handle_hint: Optional[str]) -> AccountConfig:
    if BOTS_CONFIG is None:
        raise RuntimeError(f"缺少配置文件: {CONFIG_PATH}")
    return BOTS_CONFIG.select_account(handle_hint)


@dataclass(slots=True)
class TwitterSettings:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    search_query: str
    scopes: Tuple[str, ...]
    handle: str
    persona: Optional[str] = None
    bot_usernames: Tuple[str, ...] = ()


@dataclass(slots=True)
class AppSettings:
    twitter: TwitterSettings
    openai: OpenAISettings
    poll_interval_seconds: int = 300
    max_tweets_per_run: int = 10
    state_path: str = str(VAR_DIR / "state.json")
    token_store_path: str = str(VAR_DIR / "token_state.json")

    @classmethod
    def from_env(cls) -> "AppSettings":
        def require(name: str) -> str:
            value = os.getenv(name)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {name}")
            return value

        account = _select_account(os.getenv("TWITTER_HANDLE"))
        config = BOTS_CONFIG
        if config is None:
            raise RuntimeError(f"缺少配置文件: {CONFIG_PATH}")

        twitter = TwitterSettings(
            client_id=require("TWITTER_CLIENT_ID"),
            client_secret=require("TWITTER_CLIENT_SECRET"),
            access_token=account.access_token,
            refresh_token=account.refresh_token,
            search_query=account.search_query,
            scopes=tuple(os.getenv("TWITTER_SCOPES", "").split()),
            handle=account.handle,
            persona=account.persona,
            bot_usernames=config.ignore_handles,
        )

        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_settings = OpenAISettings(
            api_key=openai_api_key.strip() if openai_api_key else None,
            model=config.models.reply_model,
            classifier_model=config.models.classifier_model,
        )

        poll_interval_default = config.defaults.poll_interval_seconds
        max_tweets_default = config.defaults.max_tweets_per_run

        poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", poll_interval_default))
        max_tweets = int(os.getenv("MAX_TWEETS_PER_RUN", max_tweets_default))

        return cls(
            twitter=twitter,
            openai=openai_settings,
            poll_interval_seconds=poll_interval,
            max_tweets_per_run=max_tweets,
        )
