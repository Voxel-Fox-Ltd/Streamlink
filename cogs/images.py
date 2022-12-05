from typing import Optional
import logging
import io

import aiohttp
from PIL import Image

from . import utils


log = logging.getLogger("streamlink.cogs.images")


async def handle_redemption(
        twitch: utils.TwitchConnector,
        oauth: utils.TwitchOauth,
        redemption: utils.types.ChannelPointsRedemption) -> Optional[bool]:
    """
    Open images on screen when required.
    """

    # Check the title of the reward
    reward_title = redemption['reward']['title']
    if not reward_title.startswith("Show image"):
        return None

    # Check if the user is a subscriber
    broadcaster_id = redemption['channel_id']
    user_id = redemption['user']['id']
    if not await oauth.is_subscriber(None, broadcaster_id, user_id):
        username = redemption['user']['display_name']
        await twitch.send_message(
            (
                f"Sorry @{username}, you need to be a "
                f"subscriber to use this reward."
            )
        )
        return False

    # Get the image we want to show
    async with aiohttp.ClientSession() as session:
        try:
            resp = await session.get(redemption['user_input'])
            resp.raise_for_status()
            image_bytes = await resp.read()
        except Exception as e:
            return False

    # And show it
    im = Image.open(io.BytesIO(image_bytes))
    im.show(title=redemption['user']['display_name'])
    return True
