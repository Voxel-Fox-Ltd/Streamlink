from __future__ import annotations

import asyncio
import os
from typing import Dict, List
import logging
import sys
import argparse
import pathlib
from urllib.parse import urlencode
import random
import re
import textwrap

from aiohttp import web
import dotenv
import emoji
import toml
import vlc

from _types import Limits, ChannelPointsRewardCreatePayload, Settings
from twitch import TwitchConnector, TwitchOauth


parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", nargs="?", default="INFO")
parser.add_argument("--validate-token", action="store_true", default=False)


dotenv.load_dotenv()
log = logging.getLogger("streamlink")
ENV_FILE_PATH = pathlib.Path(__file__).parent.resolve() / ".env"
SETTINGS_FILE_PATH = pathlib.Path(__file__).parent.resolve() / "settings.toml"
TTS_PROCESS_QUEUE: List[asyncio.Task] = []
AUDIO_OUTPUT_DEVICES: Dict[str, bytes] = {}


def create_play_sound(title: str, **kwargs) -> ChannelPointsRewardCreatePayload:
    return {
        "title": f"Play sound: {title}",
        "cost": kwargs.get("cost", 69),
        "background_color": kwargs.get("background_color", "#B00B69"),
        "is_user_input_required": False,
        "is_global_cooldown_enabled": kwargs.get("is_global_cooldown_enabled", True),
        "global_cooldown_seconds": kwargs.get("global_cooldown_seconds", 60),
    }


REWARDS: List[ChannelPointsRewardCreatePayload] = [
    create_play_sound("laughtrack"),
    create_play_sound("shotgun"),
    create_play_sound("jab"),
    create_play_sound("police siren"),
    create_play_sound("vine boom"),
    create_play_sound("Roblox death"),
    create_play_sound("rimshot"),
    create_play_sound("uwu"),
    create_play_sound("bruh"),
    create_play_sound("aughhhhh"),
    create_play_sound("Spongebob disappointed"),
    create_play_sound("oh my god"),
    create_play_sound("a bean"),
    create_play_sound("I can't believe you've done this"),
    create_play_sound("clown"),
    create_play_sound("boo"),
    create_play_sound("hello there"),
    create_play_sound("airhorn"),
]


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


def get_audio_devices() -> Dict[str, bytes]:
    """
    Get all of the registered audio devices in the system.
    """

    # Make a VLC instance
    vlc_instance: vlc.Instance = vlc.Instance()
    player: vlc.MediaPlayer = vlc_instance.media_player_new()

    # List the devices that are registed
    devices: Dict[str, bytes] = {}
    mods = player.audio_output_device_enum()
    if mods:
        index = 0
        mod = mods
        while mod:
            mod = mod.contents
            desc = mod.description.decode('utf-8', 'ignore')
            # print(f'index = {index}, desc = {desc}')
            devices[desc] = mod.device
            mod = mod.next
            index += 1

    # Free devices
    # I don't know what this does, but it's there
    vlc.libvlc_audio_output_device_list_release(mods)

    # And done
    return devices

def get_chat_output_id() -> bytes:
    data = get_settings()
    return AUDIO_OUTPUT_DEVICES.get(data['Chat Output'], b'')


def get_sound_output_id() -> bytes:
    data = get_settings()
    return AUDIO_OUTPUT_DEVICES.get(data['Sound Output'], b'')


def get_settings() -> Settings:
    """
    Read and return the settings file.
    """

    with open(SETTINGS_FILE_PATH) as a:
        return toml.load(a)  # type: ignore


def tts_text_replacement(text: str) -> str:
    """
    Replace some common words with things the TTS can actually say.
    """

    # Get settings
    settings = get_settings()

    # Remove the reply function
    if settings['Ignore Replies'] and text.startswith("@"):
        text = text.split(" ", 1)[1]

    # Get the list of replacememnts
    replacements = settings['Word Replacements']

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
    for i, o in settings['Regex Replacements'].items():
        text = re.sub(
            i,
            o,
            text,
            count=0,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    # Remove the emojis
    if settings['Ignore Emojis']:
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
    if username.lower() in settings['Voice Overrides']:
        return settings['Voice Overrides'][username.lower()]

    # Otherwise, just return the default
    r = random.Random(username + "a")
    return r.choice(list(ALL_VOICES.keys()))


def get_pitch_shift(username: str) -> float:
    """
    Get a pitch shift for a given username.
    """

    # See if we have an override
    settings = get_settings()
    if username.lower() in settings['Pitch Overrides']:
        return settings['Pitch Overrides'][username.lower()]

    # Otherwise, just return the default
    r = random.Random(username + "a")
    return r.choice(list(range(-10, 10, 2))) / 10


async def handle_run_tts(
        message: str,
        limits: Limits,
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
    vlc_player.audio_output_device_set(None, get_chat_output_id())
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


def get_twitch_auth_redirect(queue: asyncio.Queue):
    """
    Get the code from the GET parameters of the website launched for Oauth.
    """

    async def wrapper(request: web.Request):
        if request.method == "GET":
            return web.Response(
                body=textwrap.dedent("""
                    <!DOCTYPE html>
                    <html>
                    <style>
                    body {
                        font-family: 'Century Gothic', 'Helvetica', sans-serif;
                    }
                    </style>
                    <script>
                        fetch(
                            `/${location.hash.replace('#', '?')}`,
                            {method: 'POST'},
                        ).then(() => window.close())
                    </script>
                    <h1>You may now close this window <3</h1>
                    </html>
                """),
                content_type="text/html",
            )
        # code = request.query.get("code")
        queue.put_nowait(request.query['access_token'])
        # queue.put_nowait(code)
        return web.Response(body="")
    return wrapper


async def twitch_message_loop(twitch: TwitchConnector):
    """
    Deal with all of the chat input from Twitch to be able to queue up all
    of the TTS messages.
    """

    # If we're gonna error anywhere, it should be here
    get_settings()

    # Loop forever
    while True:

        # Get the username and message
        user_info, chat = await twitch.chat_queue.get()

        # See if the user is blacklisted
        settings = get_settings()
        if user_info.username.lower() in settings['TTS Blacklist']:
            log.info("Skipping blacklisted user {0}".format(user_info.username))
            continue

        # Don't say messages that are commands
        elif chat.startswith("!"):
            log.info("Ignoring command")
            continue

        # Filter out links
        elif chat.startswith("http"):
            log.info("Ignoring URL")
            continue

        # Schedule our coro
        coro = handle_run_tts(
            tts_text_replacement(chat),
            {
                "max_word_count": settings['Limits']['Max Word Count'],
                "max_word_length": settings['Limits']['Max Word Length'],
            },
            get_voice(user_info.username),
            get_pitch_shift(user_info.username),
        )
        TTS_PROCESS_QUEUE.append(asyncio.Task(coro))


async def twitch_points_loop(twitch: TwitchConnector, oauth: TwitchOauth):
    """
    The main event loop for dealing with all of the message queueing system.
    """

    # Loop forever
    while True:

        # Get the messages from the point redemption
        message = await twitch.message_queue.get()
        status = None

        if message is None:
            return

        # Onto Twitch channel point redemptions
        # Get the title of the reward
        reward_title = message['data']['redemption']['reward']['title']

        # Check if it's something we care about
        if reward_title.startswith("Play sound: "):

            # Get the path to the file we want to play
            here = pathlib.Path(__file__).parent

            # Try and play it via VLC
            try:
                partial = "sounds/" + reward_title[len("Play sound: "):] + ".wav"
                filename = (here / partial).resolve()
                vlc_instance: vlc.Instance = vlc.Instance()
                vlc_player: vlc.MediaPlayer = vlc_instance.media_player_new()
                vlc_media: vlc.Media = vlc_instance.media_new(filename)
                vlc_player.set_media(vlc_media)
                vlc_player.audio_output_device_set(None, get_sound_output_id())
                vlc_player.play()
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


async def get_access_token(oauth: TwitchOauth) -> str:
    """
    Get a valid access token from the user.
    """

    # See if we have one stored
    access_token = os.getenv("TWITCH_ACCESS_TOKEN", None)

    # Nothing stored - spin up a webserver
    if not access_token:
        code_queue = asyncio.Queue[str]()
        web_app = web.Application(debug=True)
        web_app.add_routes([
            web.post("/", get_twitch_auth_redirect(code_queue)),
            web.get("/", get_twitch_auth_redirect(code_queue)),
        ])
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, port=8558)
        await site.start()

        # Ask for the auth code
        oauth.open_auth_page()
        access_token = await code_queue.get()
        await runner.cleanup()

    # We should have something - check it's valid
    else:
        log.info("Skipping webserver as we have an access token already.")

        # See if we even want to try validating it
        if parser.parse_args().validate_token:
            log.info("Validating access token...")
            if not await oauth.validate_token(access_token):

                # Token's not valid
                log.info("Stored token is not valid.")
                remove_access_token_from_env()
                return await get_access_token(oauth)  # Loop

    # We got em
    return access_token


def write_access_token_to_env(access_token: str) -> None:
    """
    Write the access token provided to the environment file.
    """

    log.info("Writing access token to .env")
    with open(ENV_FILE_PATH) as a:
        data = a.read()
    new_data = [
        i
        for i in data.strip().split("\n")
        if not i.startswith("TWITCH_ACCESS_TOKEN")
    ]
    with open(ENV_FILE_PATH, "w") as a:
        a.write("\n".join(new_data) + "\n")
        a.write(f"TWITCH_ACCESS_TOKEN={access_token}\n")


def remove_access_token_from_env() -> None:
    """
    Remove the access token from the environment file.
    """

    log.info("Removing refresh token from .env")
    with open(ENV_FILE_PATH) as a:
        data = a.read()
    new_data = [
        i
        for i in data.strip().split("\n")
        if not i.startswith("TWITCH_ACCESS_TOKEN")
    ]
    with open(ENV_FILE_PATH, "w") as a:
        a.write("\n".join(new_data) + "\n")
    os.environ["TWITCH_ACCESS_TOKEN"] = ""


async def main():
    """
    An async version of our main loop so we can await things.
    """

    # Set up our auth
    oauth = TwitchOauth(
        os.getenv("CLIENT_ID", "y4m5g5monzwb2kaxeak1bgh71erpgf"),
    )
    access_token = await get_access_token(oauth)
    write_access_token_to_env(access_token)
    assert access_token, "Missing access token"

    # Get channel ID
    try:
        channel_id, channel_name = await (
            oauth
            .get_user_id_from_token(access_token)
        )
    except Exception as e:
        log.error("Failed to get channel ID", exc_info=True)
        remove_access_token_from_env()
        input("Press enter to exit... ")
        return

    # Create the rewards as defined in the Twitch module
    await oauth.create_rewards(access_token, channel_id, REWARDS)

    # Connect to Twitch's websockets
    twitch = TwitchConnector(access_token, channel_id, channel_name)
    await twitch.run()

    # Create TTS connector
    message_loop_task = asyncio.create_task(twitch_message_loop(twitch))
    points_loop_task = asyncio.create_task(twitch_points_loop(twitch, oauth))

    # And message handling
    while True:

        # Wrap in try so we can cancel out of everything
        try:

            # See if the message loop failed
            if message_loop_task.done() and (err := message_loop_task.exception()):
                while True:
                    log.error("Message loop task failed", exc_info=err)
                    log.info("Restarting message loop in 10 seconds...")
                    await asyncio.sleep(10)
                    coro = twitch_message_loop(twitch)
                    message_loop_task = asyncio.create_task(coro)
                    await asyncio.sleep(0.1)
                    if message_loop_task.done():
                        pass
                    else:
                        log.info("Message loop restarted!")
                        break

            # Sleep so we have something to loop
            await asyncio.sleep(0.1)

            # Remove done TTS tasks from memory
            for t in TTS_PROCESS_QUEUE:
                if t.done():
                    TTS_PROCESS_QUEUE.remove(t)

        # Catch being cancelled so we can look into it
        except asyncio.CancelledError:

            # If there are any running TTS tasks, kill them one by one first
            try:
                tts_task = TTS_PROCESS_QUEUE.pop(0)
                tts_task.cancel()
                continue
            except IndexError:
                pass

            # No tasks to cancel, let's just continue as is
            message_loop_task.cancel()
            points_loop_task.cancel()
            await twitch.cleanup()
            break


if __name__ == "__main__":
    # Parse args
    args = parser.parse_args()

    # Set up loggin
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, args.loglevel.upper()),
    )

    # Get our audio devices
    AUDIO_OUTPUT_DEVICES = get_audio_devices()

    # Run our main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
