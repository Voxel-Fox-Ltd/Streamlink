from typing import Optional
import logging
import io
import re

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

    # Get our settings
    settings = utils.get_settings()

    # Get the image we want to show
    async with aiohttp.ClientSession() as session:

        # Get the user input
        image_url = redemption['user_input']

        # Check if the image is an Imgur gallery url
        if image_url.startswith("https://imgur.com/a/"):

            # Get the album ID via regex
            match = re.match(r"https://imgur\.com/a/(\w+)", image_url)
            if not match:
                return None
            album_id = match.group(1)

            # Get the album images
            url = f"https://api.imgur.com/3/gallery/album/{album_id}"
            headers = {
                "Authorization": f"Client-ID {settings['Images']['Imgur Client ID']}",
            }
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                images = data.get("images", [])

            # Check if we have images
            if not images:
                return False

            # Get the first image
            image_url = images[0]['link']

        # Check if the image is a single image Imgur link
        elif image_url.startswith("https://imgur.com/"):
            image_url = image_url.replace("imgur.com", "i.imgur.com") + ".png"

        # See if the image is a Tenor url
        elif image_url.startswith("https://tenor.com/view/"):

            # Get the direct GIF link from the Tenor API
            match = re.match(r"https://tenor\.com/view/\w+?(\d+)", image_url)
            if not match:
                return None
            gif_id = match.group(1)

            # Get the GIF
            url = f"https://api.tenor.com/v1/gifs"
            params = {
                "key": settings['Images']['Tenor API Key'],
                "ids": gif_id,
            }
            async with session.get(url, params=params) as response:
                data = await response.json()
                gifs = data.get("results", [])

            # Check if we have images
            if not gifs:
                return False

            # Get the first image
            image_url = gifs[0]['media'][0]['gif']['url']

        # Get the image
        try:
            resp = await session.get(redemption['user_input'])
            resp.raise_for_status()
            image_bytes = await resp.read()
        except Exception as e:
            log.error(f"Failed to get image: {e}")
            return False

    # And show it
    try:
        im = Image.open(io.BytesIO(image_bytes))
        im.show(title=redemption['user']['display_name'])
    except Exception as e:
        log.error(f"Error showing image: {e}")
        return False
    return True
