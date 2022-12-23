from __future__ import annotations

from typing import TYPE_CHECKING
import pathlib
import copy

import toml
import vlc

from .types import Settings

if TYPE_CHECKING:
    from .twitch import TwitchConnector


__all__ = (
    "get_settings",
    "get_chat_output_id",
    "get_sound_output_id",
    "get_audio_devices",
)


SETTINGS_FILE_PATH = (
    pathlib
    .Path(__file__)
    .parent
    .parent
    .parent
    .resolve()) / "settings.toml"


DEFAULT_SETTINGS = {
    # "Images": {
    #     "Imgur Client ID": "",
    #     "Tenor API Key": "",
    # },
    "TTS": {
        "Sound Output": "default",
        "Ignore Replies": True,
        "Ignore Emojis": True,
        "TTS Blacklist": [],
        "Limits": {
            "Max Word Count": 100,
            "Max Word Length": 15,
        },
        "Voice Overrides": {
            "mercybot77": "matthew",
        },
        # "Pitch Overrides": {},
        "Regex Replacements": {
            r"^[\? ]+$": "huh?"
        },
        "Word Replacements": {
            "im": "I'm",
            "theres": "there's",
            "tho": "though",
            "welp": "whelp",
            "ik": "I know",
            "ew": "eww",
            "uwu": "oo woo",
            "sus": "suss",
        },
    },
    "Sound Effects": {
        "Sound Output": "default",
        "Sounds": [],
    },
}


def get_audio_devices() -> dict[str, bytes]:
    """
    Get all of the registered audio devices in the system.
    """

    # Make a VLC instance
    vlc_instance: vlc.Instance = vlc.Instance()
    player: vlc.MediaPlayer = vlc_instance.media_player_new()

    # List the devices that are registed
    devices: dict[str, bytes] = {}
    mods = player.audio_output_device_enum()
    if mods:
        index = 0
        mod = mods
        while mod:
            mod = mod.contents
            desc = mod.description.decode('utf-8', 'ignore')
            devices[desc] = mod.device
            mod = mod.next
            index += 1

    # Free devices
    # I don't know what this does, but it's there
    vlc.libvlc_audio_output_device_list_release(mods)

    # And done
    return devices


def get_settings() -> Settings:
    """
    Read and return the settings file.
    """

    try:
        with open(SETTINGS_FILE_PATH) as a:
            v = toml.load(a)
    except FileNotFoundError:
        v = DEFAULT_SETTINGS.copy()
        with open(SETTINGS_FILE_PATH, "w") as a:
            toml.dump(v, a)
    fix_dict(v, DEFAULT_SETTINGS)
    return v  # pyright: ignore


def fix_dict(fix: dict, base: dict) -> None:
    """
    Recursively alter a dictionary to match the given base settings if keys
    are missing or invalid types.
    """

    for key, value in base.items():
        if key not in fix:
            fix[key] = copy.copy(value)
        elif isinstance(fix[key], dict):
            fix_dict(fix[key], value)
        elif not isinstance(fix[key], type(value)):
            fix[key] = value


def get_chat_output_id(twitch: TwitchConnector) -> bytes:
    data = get_settings()
    return twitch.AUDIO_OUTPUT_DEVICES.get(
        data['TTS']['Sound Output'],
        b'',
    )


def get_sound_output_id(twitch: TwitchConnector) -> bytes:
    data = get_settings()
    return twitch.AUDIO_OUTPUT_DEVICES.get(
        data['Sound Effects']['Sound Output'],
        b'',
    )
