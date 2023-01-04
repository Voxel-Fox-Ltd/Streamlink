import asyncio
import logging

from .utils.twitch import TwitchChatter, TwitchConnector, TwitchOauth
from .utils.settings import get_settings


log = logging.getLogger("streamlink.cogs.customcommands")


async def handle_message(
        twitch: TwitchConnector,
        oauth: TwitchOauth,
        user_info: TwitchChatter,
        chat: str) -> asyncio.Task[bool] | None:
    """
    Handle a message from chat.
    """

    # Make sure we've got a command
    command, *args = chat.split(" ")
    if not command.startswith("!"):
        return
    command = command[1:]
    if not command:
        return

    # Get the settings
    settings = get_settings()

    # See if we've got anything
    real_commands = settings.get('Commands', {})
    for name, response in real_commands.items():
        if command.casefold() == name.casefold():
            log.info(f"Running output for {name} command")
            await twitch.send_message(response)
            return
