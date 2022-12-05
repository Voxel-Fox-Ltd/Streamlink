from typing import Dict
import random
import re
import asyncio
from urllib.parse import urlencode
import logging

import vlc
import emoji

from .utils import types
from .utils.twitch import TwitchChatter, TwitchConnector, TwitchOauth
from .utils.settings import get_settings, get_chat_output_id


log = logging.getLogger("streamlink.cogs.tts")


ALL_VOICES = {
    "matthew": ("Matthew", "1"),
    "brian": ("Brian", "1.1"),
    "amy": ("Amy", "1"),
    "emma": ("Emma", "1"),
    "geraint": ("Geraint", "1.1"),
    "russell": ("Russell", "1"),
    "nicole": ("Nicole", "1"),
    "joey": ("Joey", "1.2"),
    "justin": ("Justin", "1"),  # TikTok voice
    "joanna": ("Joanna", "1"),
    "kendra": ("Kendra", "1"),
    "kimberly": ("Kimberly", "1.2"),
    "salli": ("Salli", "1.1"),
}


def tts_text_replacement(text: str) -> str:
    """
    Replace some common words with things the TTS can actually say.
    """

    # Get settings
    settings = get_settings()

    # Remove the reply function
    if settings['TTS']['Ignore Replies'] and text.startswith("@"):
        text = text.split(" ", 1)[1]

    # Get the list of replacememnts
    replacements = settings['TTS']['Word Replacements']

    # Set up our regex function
    def replacement_function(match):
        replacement = replacements[match.group(2).strip().lower()]
        if isinstance(replacement, list):
            replacement = random.choice(replacement)
        return match.group(1) + replacement

    # Escape all of our keys
    keys = [re.escape(i) for i in replacements.keys()]

    # Do the regex sub
    text = re.sub(
        "(\\W|^)(" + "|".join(keys) + ")(?=$|\\W)",
        replacement_function,
        text,
        count=0,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Do our other regex sub
    for i, o in settings['TTS']['Regex Replacements'].items():
        text = re.sub(
            i,
            o if isinstance(o, str) else random.choice(o),
            text,
            count=0,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    # Remove the emojis
    if settings['TTS']['Ignore Emojis']:
        for i in emoji.distinct_emoji_list(text):
            text = text.replace(i, " ")

    # And done
    return text


def get_voice(username: str) -> str:
    """
    Get the voice for a given username.
    """

    # See if we have an override
    settings = get_settings()
    if username.lower() in settings['TTS']['Voice Overrides']:
        return settings['TTS']['Voice Overrides'][username.lower()]

    # Otherwise, just return the default
    r = random.Random(username + "a")
    return r.choice(list(ALL_VOICES.keys()))


def get_pitch_shift(username: str) -> float:
    """
    Get a pitch shift for a given username.
    """

    # See if we have an override
    settings = get_settings()
    if username.lower() in settings['TTS']['Pitch Overrides']:
        return settings['TTS']['Pitch Overrides'][username.lower()]

    # Otherwise, just return the default
    r = random.Random(username + "a")
    return r.choice(list(range(-10, 10, 2))) / 10


async def handle_run_tts(
        twitch: TwitchConnector,
        message: str,
        limits: types.Limits,
        voice_key: str = "brian",
        pitch_shift: float = 0) -> bool:
    """
    Handle a user on Twitch redeeming a run TTS reward
    """

    log.debug(f"TTS received - {message}")

    # See how long their request is
    words = message.split(" ")
    if len(words) > limits["max_word_count"]:
        log.info("Hit max word count")
        return False

    # See how long the words are
    if any(i for i in words if len(i) >= limits["max_word_length"]):
        log.info("Hit max word length")
        return False

    # Get the voice that we want to use
    voice = ALL_VOICES[voice_key]

    # Publish the voice with SE
    url = "https://api.streamelements.com/kappa/v2/speech?" + urlencode({
        "voice": voice[0],
        "text": message,
    })

    # process = await asyncio.create_subprocess_exec(
    #     "vlc",
    #     "-I",
    #     "dummy",
    #     "--dummy-quiet",
        # "--rate",
        # voice[1],
        # "--audio-filter",
        # "scaletempo_pitch",
    #     "--pitch-shift",
    #     str(pitch_shift),
    #     url,
    #     "vlc://quit",
    # )

    vlc_instance: vlc.Instance = vlc.Instance(
        "--rate",
        voice[1],
        "--audio-filter",
        "scaletempo_pitch",
    )
    vlc_player: vlc.MediaPlayer = vlc_instance.media_player_new()
    vlc_media: vlc.Media = vlc_instance.media_new(url)
    vlc_player.set_media(vlc_media)
    vlc_player.audio_output_device_set(None, get_chat_output_id(twitch))
    vlc_player.play()

    log.info("Running TTS with voice {0} - {1}".format(
        voice[0],
        message
    ))
    log.debug(url)
    try:
        await asyncio.sleep(1)
        while vlc_player.is_playing():
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        log.info("Cancelling TTS with voice {0} - {1}".format(
            voice[0],
            message
        ))
    finally:
        vlc_player.stop()
    return True


async def handle_message(
        twitch: TwitchConnector,
        oauth: TwitchOauth,
        user_info: TwitchChatter,
        chat: str) -> asyncio.Task[bool] | None:
    """
    Handle a message from chat.
    """

    # See if the user is blacklisted
    settings = get_settings()
    if user_info.username.lower() in settings['TTS']['TTS Blacklist']:
        log.info("Skipping blacklisted user {0}".format(user_info.username))
        return

    # Don't say messages that are commands
    elif chat.startswith("!"):
        log.info("Ignoring command")
        return

    # Filter out links
    elif chat.startswith("http"):
        log.info("Ignoring URL")
        return

    # Run our coro
    coro = handle_run_tts(
        twitch,
        tts_text_replacement(chat),
        {
            "max_word_count": settings['TTS']['Limits']['Max Word Count'],
            "max_word_length": settings['TTS']['Limits']['Max Word Length'],
        },
        get_voice(user_info.username),
        get_pitch_shift(user_info.username),
    )
    return asyncio.create_task(coro)
