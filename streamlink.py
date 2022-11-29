from __future__ import annotations

import asyncio
import os
from typing import Coroutine, List, Optional, Dict
import logging
import sys
import argparse
import pathlib
from urllib.parse import urlencode
import random
import re
import json

from aiohttp import web
import dotenv
import emoji

from _types import ChannelPointsEventMessage, Limits
from models import CleanupMixin
from twitch import TwitchConnector, TwitchOauth


dotenv.load_dotenv()
log = logging.getLogger("streamlink")
ENV_FILE_PATH = pathlib.Path(__file__).parent.resolve() / ".env"
BLACKLIST_FILE_PATH = pathlib.Path(__file__).parent.resolve() / "blacklist.txt"
REPLACEMENT_FILE_PATH = pathlib.Path(__file__).parent.resolve() / "replacements.json"


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
    # "ivy": ("Ivy", "1"),  # TikTok voice
    "joanna": ("Joanna", "1"),
    "kendra": ("Kendra", "1"),
    "kimberly": ("Kimberly", "1.2"),
    "salli": ("Salli", "1.1"),
}
VOICE_OVERRIDES = {
    "mercybot77": "matthew",
    "maxlovetoby": "russell",
    "glooomygoose": "justin",
    "deejaym2k": "brian",
    "kepic2": "salli",
    "marshshshshshshsh": "kimberly",
    "vineyboi6": "russell",
    "shallottheprince": "brian",
    "mellow": "kimberly",
    "boo_wh0": "russell",
    "thedevpanda": "geraint",
}
TTS_QUEUE: asyncio.Queue[Coroutine] = asyncio.Queue()
TTS_LOOP_TASK: Optional[asyncio.Task] = None


def get_blacklist() -> List[str]:
    """
    Get the blacklist of users.
    """

    # Get the blacklist
    with open(BLACKLIST_FILE_PATH) as a:
        return a.read().strip().split("\n")


def get_replacement_list() -> Dict[str, str]:
    """
    Get the replacement dict
    """

    # Get the blacklist
    with open(REPLACEMENT_FILE_PATH) as a:
        return json.load(a)


def tts_text_replacement(text: str) -> str:
    """
    Replace some common words with things the TTS can actually say.
    """

    # Remove the reply function
    if text.startswith("@"):
        text = text.split(" ", 1)[1]

    # Get the list of replacememnts
    replacements = get_replacement_list()

    # Set up our regex function
    def replacement_function(match):
        replacement = replacements[match.group(2).strip().lower()]
        if isinstance(replacement, list):
            replacement = random.choice(replacement)
        return match.group(1) + replacement

    # Escape all of our keys
    keys = [re.escape(i) for i in replacements.keys()]

    # Do the regex sub
    new_text = re.sub(
        "(\\W|^)(" + "|".join(keys) + ")(?=$|\\W)",
        replacement_function,
        text,
        count=0,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Remove the emojis
    for i in emoji.distinct_emoji_list(new_text):
        new_text = new_text.replace(i, " ")

    # And done
    return new_text


def get_voice(username: str) -> str:
    """
    Get the voice for a given username.
    """

    # See if we have an override
    if username.lower() in VOICE_OVERRIDES:
        return VOICE_OVERRIDES[username.lower()]

    # Otherwise, just return the default
    r = random.Random(username + "a")
    return r.choice(list(ALL_VOICES.keys()))


def get_pitch_shift(username: str) -> float:
    """
    Get a pitch shift for a given username.
    """

    r = random.Random(username + "a")
    return r.choice(list(range(-10, 10, 2))) / 10


async def handle_run_tts(
        message: ChannelPointsEventMessage | str,
        limits: Optional[Limits] = None,
        voice_key: str = "brian",
        pitch_shift: float = 0) -> bool:
    """
    Handle a user on Twitch redeeming a run TTS reward
    """

    # See if the colour is valid
    user_input: str
    if isinstance(message, str):
        user_input = message
    else:
        user_input = message['data']['redemption']['user_input']
    log.debug(f"TTS received - {user_input}")

    # Validate limits
    limits = limits or {
        "max_word_count": 20,
        "max_word_length": 16,
    }
    login: str
    if isinstance(message, str):
        login = ""
    else:
        login = message['data']['redemption']['user']['login']
    limit_overrides = [
        "",
        "voxelfoxkae",
    ]

    # See if they bypass the overrides
    if login not in limit_overrides:

        # See how long their request is
        words = user_input.split(" ")
        if len(words) > limits["max_word_count"]:
            log.info("Hit max word count")
            return False

        # See how long the words are
        if any(i for i in words if len(i) >= limits["max_word_length"]):
            log.info("Hit max word length")
            return False

        # Add an emoji filter
        if emoji.emoji_count(user_input) > 0:
            log.info("Hit emoji filter")
            return False

    # Set up some voices
    voice = ALL_VOICES[voice_key]

    # Publish the voice with SE
    url = "https://api.streamelements.com/kappa/v2/speech?" + urlencode({
        "voice": voice[0],
        "text": user_input,
    })
    future = asyncio.create_subprocess_exec(
        "vlc",
        "-I",
        "dummy",
        "--dummy-quiet",
        "--rate",
        voice[1],
        "--audio-filter",
        "scaletempo_pitch",
        "--pitch-shift",
        str(pitch_shift),
        url,
        "vlc://quit",
    )
    log.info("Added text to TTS with voice {0} - {1}".format(
        voice[0],
        user_input
    ))
    task = asyncio.get_running_loop().create_task(future)
    try:
        await asyncio.wait([task])
    except asyncio.CancelledError:
        task.cancel()
        raise
    return True


def get_twitch_auth_redirect(queue: asyncio.Queue):
    async def wrapper(request: web.Request):
        code = request.query.get("code")
        queue.put_nowait(code)
        return web.Response(body="You may now close this window.")
    return wrapper


async def tts_loop():
    """
    Read from the TTS queue and play the TTS.
    """

    while True:
        coro = await TTS_QUEUE.get()
        task = asyncio.Task(coro)
        await asyncio.sleep(0.1)


async def main(args: argparse.Namespace):
    """
    An async version of our main loop so we can await things.
    """

    global TO_CLEANUP
    global oauth
    global twitch
    global razer
    global tts_engine
    global TTS_LOOP_TASK

    # See if we have a stored access token
    oauth = TwitchOauth(os.getenv("CLIENT_ID", ""), os.getenv("CLIENT_SECRET", ""))
    refresh_token = os.getenv("TWITCH_REFRESH_TOKEN", None)

    # We have an access token
    if refresh_token:
        log.info("Skipping webserver as we have a refresh token already.")
        try:
            access_token, refresh_token = await oauth.get_access_token_from_refresh(refresh_token)
        except:
            access_token = None

    # We don't have an access token
    else:

        # Start a webserver so we don't need to ask for an auth code
        code_queue = asyncio.Queue[str]()
        web_app = web.Application(debug=True)
        web_app.add_routes([
            web.get("/", get_twitch_auth_redirect(code_queue))
        ])
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, port=8558)
        await site.start()

        # Ask for the auth code
        oauth.open_auth_page()
        auth_code = await code_queue.get()
        await runner.cleanup()

        # Get an access token and channel ID
        access_token, refresh_token = await oauth.get_access_token_from_code(auth_code)

    # Store new refresh token
    with open(ENV_FILE_PATH) as a:
        data = a.read()
    new_data = [
        i
        for i in data.strip().split("\n")
        if not i.startswith("TWITCH_REFRESH_TOKEN")
    ]
    with open(ENV_FILE_PATH, "w") as a:
        a.write("\n".join(new_data) + "\n")
        a.write(f"TWITCH_REFRESH_TOKEN={refresh_token}\n")
    assert access_token, "Missing access token"

    # Get channel ID
    try:
        channel_id, channel_name = await oauth.get_user_id_from_token(access_token)
    except Exception as e:
        log.error("Failed to get channel ID", exc_info=True)
        with open(ENV_FILE_PATH) as a:
            data = a.read()
        new_data = [
            i
            for i in data.strip().split("\n")
            if not i.startswith("TWITCH_REFRESH_TOKEN")
        ]
        log.info("Removing refresh token from .env")
        with open(ENV_FILE_PATH, "w") as a:
            a.write("\n".join(new_data) + "\n")
        input("Press enter to exit... ")
        exit(1)

    # Create the rewards
    await oauth.create_reward(access_token, channel_id)

    # Create Twitch connector
    twitch = TwitchConnector(access_token, channel_id, channel_name)
    await twitch.run()
    TO_CLEANUP.append(twitch)

    # Create TTS connector
    TTS_LOOP_TASK = asyncio.create_task(tts_loop())

    # And message handling
    while True:

        # Sleep
        await asyncio.sleep(0.1)

        # Get the messages
        message = None
        if not twitch.message_queue.empty():
            message = await twitch.message_queue.get()
        status = None

        # Just say all the chat messages
        while not twitch.chat_queue.empty():
            username, chat = await twitch.chat_queue.get()
            if username.lower() in get_blacklist():
                log.info("Skipping blacklisted user {0}".format(username))
                continue
            elif chat.startswith("!"):
                log.info("Ignoring command")
                continue
            elif chat.startswith("http"):
                log.info("Ignoring URL")
                continue
            coro = handle_run_tts(
                tts_text_replacement(chat),
                {
                    "max_word_count": 50,
                    "max_word_length": 16,
                },
                get_voice(username),
                get_pitch_shift(username),
            )
            TTS_QUEUE.put_nowait(coro)

        if message is None:
            continue

        # Make sure it's a redemption I want
        reward_title = message['data']['redemption']['reward']['title']
        if reward_title.startswith("Play sound: "):
            here = pathlib.Path(__file__).parent.resolve()
            try:
                filename = "sounds/" + reward_title[len("Play sound: "):] + ".wav"
                future = asyncio.create_subprocess_exec(
                    "vlc",
                    "-I",
                    "dummy",
                    "--dummy-quiet",
                    str(here / filename),
                    "vlc://quit",
                )
                asyncio.get_running_loop().create_task(future)
                status = True
            except Exception as e:
                log.error("Error playing sound file", exc_info=e)
                status = False

        # See if we should mark it as redeemed
        if status is not None:
            redemption_id = message['data']['redemption']['id']
            reward_id = message['data']['redemption']['reward']['id']
            await oauth.update_redemption_status(
                twitch.access_token,
                redemption_id,
                twitch.channel_id,
                reward_id,
                "FULFILLED" if status else "CANCELED",
            )

        # And we done
        continue


def main_nowait(args: argparse.Namespace):
    """
    When we start the script, this is the method that runs. This starts
    our asyncio loop.
    """

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main(args))
    except KeyboardInterrupt:
        pass
    for i in TO_CLEANUP:
        try:
            i.cleanup()
        except Exception as e:
            log.error(f"Hit error cleaning up - {e}")


def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loglevel", nargs="?", default="INFO")
    return parser


TO_CLEANUP: List[CleanupMixin] = []  #: A list of things to clean up on stopping the script.
oauth: TwitchOauth  #: The oauth connection object.
twitch: TwitchConnector  #: The Twitch connection object.


if __name__ == "__main__":
    args = setup_args().parse_args()
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, args.loglevel.upper()),
    )
    main_nowait(args)
