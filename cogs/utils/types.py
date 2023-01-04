from typing import Literal, TypedDict, Optional


_SettingsTTSLimit = TypedDict(
    "_SettingsTTSLimit",
    {
        "Max Word Count": int,
        "Max Word Length": int,
    },
)


_SettingsTTS = TypedDict(
    "_SettingsTTS",
    {
        "Enabled": bool,
        "Point Cost": int,
        "Lock": Literal["none", "per_person", "global"],
        "Sound Output": str,
        "Ignore Replies": bool,
        "Ignore Emojis": bool,
        "TTS Blacklist": list[str],
        "Limits": _SettingsTTSLimit,
        "Voice Overrides": dict[str, str],
        "Pitch Overrides": dict[str, float],
        "Regex Replacements": dict[str, str | list[str]],
        "Word Replacements": dict[str, str | list[str]],
    },
)


_SettingsSoundEffectsSound = TypedDict(
    "_SettingsSoundEffectsSound",
    {
        "name": str,
        "path": str,
        "cost": int,
    }
)


_SettingsSoundEffects = TypedDict(
    "_SettingsSoundEffects",
    {
        "Sound Output": str,
        "Sounds": list[_SettingsSoundEffectsSound]
    }
)


_SettingsImages = TypedDict(
    "_SettingsImages",
    {
        "Imgur Client ID": str,
        "Tenor API Key": str,
    },
)


Settings = TypedDict(
    "Settings",
    {
        "Images": _SettingsImages,
        "TTS": _SettingsTTS,
        "Sound Effects": _SettingsSoundEffects,
        "Commands": dict[str, str],
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
    is_sub_only: bool


class ChannelPointsRewardCreatePayload(_ChannelPointsRewardCreatePayloadOptional):
    title: str
    cost: int


class ChannelPointsRewardPayload(ChannelPointsRewardCreatePayload):
    id: str
    is_paused: bool
    is_in_stock: bool
    default_image: Image
    image: Image
    is_sub_only: bool
    cooldown_expires_at: Optional[str]
