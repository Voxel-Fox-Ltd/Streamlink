from typing import Optional
import logging

import asyncio
import aiohttp
from discord.ext import vbu

from models import CleanupMixin


COLOURS_BY_NAME = vbu.converters.ColourConverter.COLOURS_BY_NAME
log = logging.getLogger("streamlink.razer")


class RazerChromaConnector(CleanupMixin):
    """
    A connector for Razer Chroma so that we can interface with my headphones.
    """

    KRAKEN_KITTY_ID = "FB357780-4617-43A7-960F-D1190ED54806"

    def __init__(self):
        self.uri = None
        self.heartbeat_task = None
        # self.colour_change_task = None
        self.session = None

    async def run(self):
        """
        Connect to Razer, send our identify, create a heartbeat.
        """

        self.session = aiohttp.ClientSession()
        self.uri = await self.identify()
        self.heartbeat_task = asyncio.get_event_loop().create_task(self.heartbeat())
        # self.colour_change_task = asyncio.get_event_loop().create_task(self.change_colour_loop())

    def cleanup(self):
        """
        Cancel the runnign tasks, delete the session.
        """

        log.info("Cancelling tasks")
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        log.info("Deleting session")
        if self.session and self.uri:
            coro = self.session.delete(self.uri)
            asyncio.get_event_loop().run_until_complete(coro)

    async def identify(self):
        """
        Send the identify data to Razer so they know who we are.
        """

        identify_data = {
            "title": "VFL Chroma Streamlink",
            "description": "it's owo time",
            'author': {
                "name": "Kae Bartlett",
                "contact": "kae@voxelfox.co.uk",
            },
            "device_supported": ["headset"],
            "category": "application",
        }
        log.info("Identifying...")
        assert self.session
        url = 'http://localhost:54235/razer/chromasdk'
        async with self.session.post(url, json=identify_data) as r:
            data = await r.json()
        log.info(f"Identified {identify_data['title']} - {data}")
        return data['uri']

    async def heartbeat(self):
        """
        Create a heartbeat.
        """

        await asyncio.sleep(2)
        async with aiohttp.ClientSession() as session:
            while True:
                log.debug("Sending hearbeat...")
                await session.put(f"{self.uri}/heartbeat")
                log.debug("Heartbeat sent")
                await asyncio.sleep(10)

    async def set_colour(
            self,
            c1: int,
            c2: Optional[int] = None,
            c3: Optional[int] = None,
            c4: Optional[int] = None):
        """
        Send a hex colour change.
        """

        log.debug(f"Setting colour to #{c1:0>6X}")
        c1 = (((c1 >> 16) & 0xff)) | (((c1 >> 8) & 0xff) << 8) | (((c1 >> 0) & 0xff) << 16)
        c2 = ((((c2 or c1) >> 16) & 0xff)) | ((((c2 or c1) >> 8) & 0xff) << 8) | ((((c2 or c1) >> 0) & 0xff) << 16)
        c3 = ((((c3 or c1) >> 16) & 0xff)) | ((((c3 or c1) >> 8) & 0xff) << 8) | ((((c3 or c1) >> 0) & 0xff) << 16)
        c4 = ((((c4 or c1) >> 16) & 0xff)) | ((((c4 or c1) >> 8) & 0xff) << 8) | ((((c4 or c1) >> 0) & 0xff) << 16)
        assert self.session
        data = await self.session.put(
            f"{self.uri}/devid={self.KRAKEN_KITTY_ID}",
            json={
                # "effect": "CHROMA_STATIC",
                # "param": {
                #     "color": colour,
                # },
                "effect": "CHROMA_CUSTOM",
                "param": [c1, c2, c3, c4]
            },
        )
        log.info(await data.json())

    async def change_colour_loop(self):
        """
        Change colours on a loop.
        """

        while True:
            for i in [0xff0000, 0x00ff00, 0x0000ff]:
                await self.set_colour(i)
                await asyncio.sleep(3)


def parse_colour(value: str) -> Optional[int]:
    colour = None
    try:
        colour = COLOURS_BY_NAME[value.lower().strip()]
    except KeyError:
        pass

    # It's not - see if it's a hex code
    if colour is None:
        try:
            colour = int(value.lstrip('#'), 16)
        except ValueError:

            # It's not a hex code - let's just leave
            log.info(f"Invalid colour - {value}")
            return None
    return colour
