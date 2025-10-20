"""Configuration helpers for the auto-reply bot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


load_dotenv()

DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_CLASSIFIER_MODEL = "gpt-5-nano"
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


@dataclass(slots=True)
class OpenAISettings:
    api_key: Optional[str] = field(default=None, repr=False)
    model: str = DEFAULT_OPENAI_MODEL
    reply_style_prompt: str = DEFAULT_REPLY_PROMPT
    classifier_model: str = DEFAULT_CLASSIFIER_MODEL
    classification_prompt: str = DEFAULT_CLASSIFICATION_PROMPT


@dataclass(slots=True)
class TwitterSettings:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    search_query: str
    scopes: Tuple[str, ...]
    bot_usernames: Tuple[str, ...] = ()


@dataclass(slots=True)
class AppSettings:
    twitter: TwitterSettings
    openai: OpenAISettings
    poll_interval_seconds: int = 300
    max_tweets_per_run: int = 10
    state_path: str = "app/post/var/state.json"
    token_store_path: str = "app/post/var/token_state.json"

    @classmethod
    def from_env(cls) -> "AppSettings":
        def require(name: str) -> str:
            value = os.getenv(name)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {name}")
            return value

        bot_usernames_env = require("TWITTER_BOT_USERNAME")
        bot_usernames_parts = [part.strip() for part in bot_usernames_env.split(",")]
        if any(not part for part in bot_usernames_parts):
            raise RuntimeError("TWITTER_BOT_USERNAME 必须是用逗号分隔的用户名列表，且不允许空项")
        bot_usernames = tuple(part.lower().lstrip("@") for part in bot_usernames_parts)

        twitter = TwitterSettings(
            client_id=require("TWITTER_CLIENT_ID"),
            client_secret=require("TWITTER_CLIENT_SECRET"),
            access_token=require("TWITTER_ACCESS_TOKEN"),
            refresh_token=require("TWITTER_REFRESH_TOKEN"),
            search_query=require("TWITTER_SEARCH_QUERY"),
            scopes=tuple(os.getenv("TWITTER_SCOPES", "").split()),
            bot_usernames=bot_usernames,
        )

        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_settings = OpenAISettings(
            api_key=openai_api_key.strip() if openai_api_key else None,
        )

        poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
        max_tweets = int(os.getenv("MAX_TWEETS_PER_RUN", "10"))

        return cls(
            twitter=twitter,
            openai=openai_settings,
            poll_interval_seconds=poll_interval,
            max_tweets_per_run=max_tweets,
            state_path="app/post/var/state.json",
            token_store_path="app/post/var/token_state.json",
        )
