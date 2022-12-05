from __future__ import annotations

import asyncio
import os
from typing import Dict, List
import logging
import sys
import argparse
import pathlib
import textwrap
import glob
import importlib

from aiohttp import web
import dotenv

from cogs import utils


parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", nargs="?", default="INFO")
parser.add_argument("--validate-token", action="store_true", default=False)


dotenv.load_dotenv()
log = logging.getLogger("streamlink")
ENV_FILE_PATH = pathlib.Path(__file__).parent.resolve() / ".env"
AUDIO_OUTPUT_DEVICES: Dict[str, bytes] = {}


def create_play_sound(title: str, **kwargs) -> utils.types.ChannelPointsRewardCreatePayload:
    return {
        "title": f"Play sound: {title}",
        "cost": kwargs.get("cost", 69),
        "background_color": kwargs.get("background_color", "#B00B69"),
        "is_user_input_required": False,
        "is_global_cooldown_enabled": kwargs.get("is_global_cooldown_enabled", True),
        "global_cooldown_seconds": kwargs.get("global_cooldown_seconds", 60),
    }


def create_rewards() -> List[utils.types.ChannelPointsRewardCreatePayload]:
    sounds = [
        create_play_sound(i['name'], cost=i['cost'])
        for i in utils.get_settings()["Sound Effects"].get("Sounds", list())
    ]
    return sounds + [
        {
            "title": "Show image",
            "cost": 500,
            "background_color": "#18E2BC",
            "is_user_input_required": True,
        }
    ]


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


async def twitch_chat_loop(
        twitch: utils.TwitchConnector,
        oauth: utils.TwitchOauth):
    """
    Deal with all of the chat input from Twitch to be able to queue up all
    of the TTS messages.
    """

    # If we're gonna error anywhere, it should be here
    utils.get_settings()

    # Loop forever
    while True:

        # Get the username and message
        user_info, chat = await twitch.chat_queue.get()
        for i in twitch.chat_handlers:
            coro = i(twitch, oauth, user_info, chat)
            asyncio.create_task(coro)


async def handle_redemption(
        twitch: utils.TwitchConnector,
        oauth: utils.TwitchOauth,
        redemption: utils.types.ChannelPointsEventMessage,
        func) -> None:
    """
    A wrapper around a redemption to mark it as done when it's done.
    """

    status = await func(twitch, oauth, redemption['data']['redemption'])
    if status is None:
        return

    redemption_id = redemption['data']['redemption']['id']
    reward_id = redemption['data']['redemption']['reward']['id']
    await oauth.update_redemption_status(
        twitch.access_token,
        redemption_id,
        twitch.channel_id,
        reward_id,
        "FULFILLED" if status else "CANCELED",
    )


async def twitch_points_loop(
        twitch: utils.TwitchConnector,
        oauth: utils.TwitchOauth):
    """
    The main event loop for dealing with all of the message queueing system.
    """

    # Loop forever
    while True:

        # Get the messages from the point redemption
        message = await twitch.message_queue.get()
        for i in twitch.reward_handlers:
            try:
                await handle_redemption(twitch, oauth, message, i)
            except Exception as e:
                log.exception("Failed to handle redemption", exc_info=e)


async def get_access_token(oauth: utils.TwitchOauth) -> str:
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
    oauth = utils.TwitchOauth(
        os.getenv("CLIENT_ID", "y4m5g5monzwb2kaxeak1bgh71erpgf"),
    )
    access_token = await get_access_token(oauth)
    write_access_token_to_env(access_token)
    assert access_token, "Missing access token"
    oauth.access_token = access_token

    # Get channel ID
    try:
        channel_id, channel_name = await (
            oauth
            .get_user_id_from_token(access_token)
        )
    except Exception:
        log.error("Failed to get channel ID", exc_info=True)
        remove_access_token_from_env()
        input("Press enter to exit... ")
        return

    # Create the rewards as defined in the Twitch module
    log.info("Creating channel points rewards...")
    await oauth.create_rewards(
        access_token,
        channel_id,
        create_rewards(),
    )

    # Connect to Twitch's websockets
    twitch = utils.TwitchConnector(access_token, channel_id, channel_name)
    await twitch.run()
    twitch.AUDIO_OUTPUT_DEVICES = utils.get_audio_devices()  # type: ignore

    # Go through each cog and add the chat and reward handlers
    for cog in glob.glob("cogs/[!_]*.py"):
        module = importlib.import_module(cog[:-3].replace(os.sep, "."))
        if hasattr(module, "handle_message"):
            twitch.chat_handlers.append(module.handle_message)
            log.info("Loaded chat handler cog %s", module.__name__)
        if hasattr(module, "handle_redemption"):
            twitch.reward_handlers.append(module.handle_redemption)
            log.info("Loaded redemption handler cog %s", module.__name__)

    # Create TTS connector
    log.info("Starting message and point tasks...")
    message_loop_task = asyncio.create_task(twitch_chat_loop(twitch, oauth))
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
                    coro = twitch_chat_loop(twitch)
                    message_loop_task = asyncio.create_task(coro)
                    await asyncio.sleep(0.1)
                    if message_loop_task.done():
                        pass
                    else:
                        log.info("Message loop restarted!")
                        break

            # Sleep so we have something to loop
            await asyncio.sleep(0.1)

        # Catch being cancelled so we can look into it
        except asyncio.CancelledError:

            # Cancel our tasks and run our cleanups
            message_loop_task.cancel()
            points_loop_task.cancel()
            await twitch.cleanup()

            # Disable each of the added rewards
            log.info("Deleting rewards...")
            await oauth.delete_rewards(
                access_token,
                channel_id,
                create_rewards(),
            )

            # And exit
            raise


if __name__ == "__main__":
    # Parse args
    args = parser.parse_args()

    # Set up loggin
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, args.loglevel.upper()),
    )

    # Run our main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
