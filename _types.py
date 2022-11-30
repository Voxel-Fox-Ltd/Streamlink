from typing import Dict, List, Literal, TypedDict


_SettingsTTSLimit = TypedDict(
    "_SettingsTTSLimit",
    {
        "Max Word Count": int,
        "Max Word Length": int,
    },
)



Settings = TypedDict(
    "Settings",
    {
        "Chat Output": str,
        "Sound Output": str,
        "Ignore Replies": bool,
        "Ignore Emojis": bool,
        "TTS Blacklist": List[str],
        "Limits": _SettingsTTSLimit,
        "Voice Overrides": Dict[str, str],
        "Pitch Overrides": Dict[str, float],
        "Regex Replacements": Dict[str, str],
        "Word Replacements": Dict[str, str],
    },
)


RewardRedemptionStatus = Literal[
    "UNKNOWN",
    "UNFULFILLED",
    "FULFILLED",
    "CANCELED",
]


class Image(TypedDict):
    url_1x: str
    url_2x: str
    url_4x: str


class MaxPerStream(TypedDict):
    is_enabled: bool
    max_per_stream: int


class ChannelPointsReward(TypedDict):
    id: str
    channel_id: str
    title: str
    prompt: str
    cost: int
    is_user_input_required: bool
    is_sub_only: bool
    image: Image
    default_image: Image
    background_color: str
    is_enabled: bool
    is_paused: bool
    is_in_stock: bool
    max_per_stream: MaxPerStream
    should_redemptions_skip_request_queue: bool


class ChannelPointsUser(TypedDict):
    id: str
    login: str
    display_name: str


class ChannelPointsRedemption(TypedDict):
    id: str
    user: ChannelPointsUser
    channel_id: str
    redeemed_at: str
    reward: ChannelPointsReward
    user_input: str
    status: RewardRedemptionStatus


class ChannelPointsData(TypedDict):
    timestamp: str
    redemption: ChannelPointsRedemption


class ChannelPointsEventMessage(TypedDict):
    type: Literal["reward-redeemed"]
    data: ChannelPointsData


class Limits(TypedDict):
    max_word_count: int
    max_word_length: int


class _ChannelPointsRewardCreatePayloadOptional(TypedDict, total=False):
    prompt: str
    is_enabled: bool
    background_color: str
    is_user_input_required: bool
    is_max_per_stream_enabled: bool
    max_per_stream: int
    is_max_per_user_per_stream_enabled: bool
    max_per_user_per_stream: int
    is_global_cooldown_enabled: bool
    global_cooldown_seconds: int
    should_redemptions_skip_request_queue: bool


class ChannelPointsRewardCreatePayload(_ChannelPointsRewardCreatePayloadOptional):
    title: str
    cost: int
