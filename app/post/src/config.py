"""Configuration helpers for the auto-reply bot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

import yaml
from dotenv import load_dotenv


load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yml"
PROJECT_ROOT = CONFIG_PATH.parent
VAR_DIR = PROJECT_ROOT / "var"


def _normalize_handle(value: str) -> str:
    return value.lower().lstrip("@")


def token_cache_path(handle: str) -> Path:
    return VAR_DIR / f"token_{_normalize_handle(handle)}.json"


def _load_prompt_text(path_value: str, *, label: str) -> str:
    path_str = str(path_value).strip()
    if not path_str:
        raise RuntimeError(f"{label} 缺少 prompt 路径")
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise RuntimeError(f"{label} 指向的文件不存在: {path}")
    return path.read_text(encoding="utf-8")


@dataclass(slots=True)
class DefaultsConfig:
    poll_interval_seconds: int = 300
    max_tweets_per_run: int = 10


@dataclass(slots=True)
class ModelsConfig:
    reply_model: str
    classifier_model: str


@dataclass(slots=True)
class PersonaConfig:
    name: str
    reply_prompt: str
    classifier_prompt: str


@dataclass(slots=True)
class AccountConfig:
    handle: str
    persona: str
    access_token: str
    refresh_token: str
    search_query: str


@dataclass(slots=True)
class BotsConfig:
    defaults: DefaultsConfig
    models: ModelsConfig
    accounts: dict[str, AccountConfig]
    personas: dict[str, PersonaConfig]
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

        personas_raw = raw.get("personas")
        if not isinstance(personas_raw, dict) or not personas_raw:
            raise RuntimeError("config.yml 缺少 personas 节配置")
        personas: dict[str, PersonaConfig] = {}
        for name, persona_raw in personas_raw.items():
            if not isinstance(persona_raw, dict):
                raise RuntimeError(f"config.yml persona {name} 配置必须是字典")
            reply_prompt_path = persona_raw.get("reply_prompt_path")
            classifier_prompt_path = persona_raw.get("classifier_prompt_path")
            reply_prompt = _load_prompt_text(reply_prompt_path, label=f"persona {name}.reply_prompt_path")
            classifier_prompt = _load_prompt_text(
                classifier_prompt_path, label=f"persona {name}.classifier_prompt_path"
            )
            personas[name] = PersonaConfig(
                name=name,
                reply_prompt=reply_prompt,
                classifier_prompt=classifier_prompt,
            )

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
            persona = str(persona_value).strip() if persona_value else ""
            if not persona:
                raise RuntimeError("config.yml persona group 缺少 persona 字段")
            if persona not in personas:
                raise RuntimeError(f"config.yml 未定义 persona: {persona}")
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
            personas=personas,
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
    reply_style_prompt: str
    classification_prompt: str
    provider: str = "openai"
    api_key: Optional[str] = field(default=None, repr=False)


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
    persona: str
    bot_usernames: Tuple[str, ...] = ()


@dataclass(slots=True)
class AppSettings:
    twitter: TwitterSettings
    openai: OpenAISettings
    state_path: str
    token_store_path: str
    poll_interval_seconds: int = 300
    max_tweets_per_run: int = 10

    @classmethod
    def from_env(cls, *, handle: Optional[str] = None) -> "AppSettings":
        def require(name: str) -> str:
            value = os.getenv(name)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {name}")
            return value

        account_hint = handle or os.getenv("TWITTER_HANDLE")
        account = _select_account(account_hint)
        config = BOTS_CONFIG
        if config is None:
            raise RuntimeError(f"缺少配置文件: {CONFIG_PATH}")
        persona_config = config.personas.get(account.persona)
        if persona_config is None:
            raise RuntimeError(f"persona {account.persona} 未在 config.yml 的 personas 中定义")

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

        token_path = token_cache_path(account.handle)
        normalized_handle = account.handle.lower().lstrip("@")
        state_path = VAR_DIR / f"state_{normalized_handle}.json"

        provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        if provider not in {"openai", "gemini"}:
            raise RuntimeError(f"不支持的 LLM_PROVIDER: {provider}")

        if provider == "gemini":
            api_key_value = os.getenv("GEMINI_API_KEY")
            if not api_key_value:
                raise RuntimeError("缺少 GEMINI_API_KEY，用于 Gemini 模型调用")
        else:
            api_key_value = os.getenv("OPENAI_API_KEY")

        openai_settings = OpenAISettings(
            model=config.models.reply_model,
            classifier_model=config.models.classifier_model,
            reply_style_prompt=persona_config.reply_prompt,
            classification_prompt=persona_config.classifier_prompt,
            provider=provider,
            api_key=api_key_value.strip() if api_key_value else None,
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
            state_path=str(state_path),
            token_store_path=str(token_path),
        )
