from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

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

    with open(SETTINGS_FILE_PATH) as a:
        return toml.load(a)


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
