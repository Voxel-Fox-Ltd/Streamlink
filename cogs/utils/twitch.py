import json
import webbrowser
from urllib.parse import quote, urlencode
from typing import TYPE_CHECKING, ClassVar, List, Optional, Tuple
import asyncio
import logging
import re
import dataclasses

import aiohttp
import websockets
from typing_extensions import Self

from .types import (
    ChannelPointsEventMessage,
    ChannelPointsRewardCreatePayload,
    RewardRedemptionStatus,
    ChannelPointsRewardPayload,
)

if TYPE_CHECKING:
    from websockets.client import WebSocketClientProtocol


__all__ = (
    "TwitchChatter",
    "TwitchOauth",
    "TwitchConnector",
)


log = logging.getLogger("streamlink.twitch")


TEXT_MESSAGE_REGEX = re.compile(
    (
        r"(?:@(?P<tags>.+?) )?:(?P<username>.+?)!.+?@.+?\.tmi\.twitch\.tv "
        r"PRIVMSG #(?P<channel>.+?) :(?P<message>.+)"
    )
)


@dataclasses.dataclass
class TwitchChatter:
    username: str
    colour: Optional[str] = None
    moderator: bool = False
    subscriber: bool = False
    vip: bool = False

    @classmethod
    def parse(cls, username: str, line: str) -> Self:
        """
        Parse a line from Twitch.
        """

        keys = {
            i.split("=")[0]: i.split("=")[1]
            for i in line.split(";")
        }
        colour = keys.get("color") or None
        moderator = keys.get("mod", "0") == "1"
        subscriber = keys.get("subscriber", "0") == "1"
        vip = keys.get("vip", "0") == "1"
        return cls(
            username=username,
            colour=colour,
            moderator=moderator,
            subscriber=subscriber,
            vip=vip,
        )


class TwitchOauth:
    """
    A client to handle Twitch API requests.
    """

    def __init__(
            self,
            client_id: str,
            client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None

    def open_auth_page(self):
        """
        Open the "login with Twitch" authorize page for this app.
        """

        url = "https://id.twitch.tv/oauth2/authorize?" + urlencode({
            "client_id": self.client_id,
            "redirect_uri": "http://localhost:8558",
            "response_type": "token",
            "scope": " ".join([
                "channel:read:redemptions",
                "channel:manage:redemptions",
                "chat:read",
                "chat:edit",
            ]),
        })
        webbrowser.open_new(url)

    async def validate_token(self, access_token: Optional[str]) -> bool:
        """
        Checks whether a given access token is still valid.
        """

        headers = {
            "Authorization": f"Bearer {access_token or self.access_token}",
        }
        async with aiohttp.ClientSession() as session:
            url = "https://id.twitch.tv/oauth2/validate"
            site = await session.post(url, headers=headers)
        return site.ok

    async def get_access_token_from_code(self, code: str) -> Tuple[str, str]:
        """
        Take the code from the authorization and return the access token from it.
        """

        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8558"
        }
        async with aiohttp.ClientSession() as session:
            url = "https://id.twitch.tv/oauth2/token"
            site = await session.post(url, params=params)
        data = await site.json()
        return data['access_token'], data['refresh_token']

    async def get_access_token_from_refresh(self, code: str) -> Tuple[str, str]:
        """
        Get the access token given a refresh token.
        """

        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": quote(code),
            "grant_type": "refresh_token",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with aiohttp.ClientSession() as session:
            url = "https://id.twitch.tv/oauth2/token"
            site = await session.post(url, data=params, headers=headers)
        data = await site.json()
        return data['access_token'], data['refresh_token']

    async def get_user_id_from_token(self, token: str) -> Tuple[str, str]:
        """
        Ask the Twitch API for the ID of the authenticated user.
        """

        headers = {
            "Authorization": f"Bearer {token or self.access_token}",
            "Client-Id": self.client_id,
        }
        async with aiohttp.ClientSession() as session:
            url = "https://api.twitch.tv/helix/users"
            site = await session.get(url, headers=headers)
        try:
            d = (await site.json())['data'][0]
        except Exception as e:
            log.error(
                "Failed to get user ID (%s)" % (await site.json()),
                exc_info=e,
            )
            raise
        return d['id'], d['login']

    async def create_rewards(
            self,
            token: Optional[str],
            channel_id: str,
            rewards: List[ChannelPointsRewardCreatePayload]) -> bool:
        """
        Create the rewards.
        """

        headers = {
            "Authorization": f"Bearer {token or self.access_token}",
            "Client-Id": self.client_id,
        }
        params = {
            "broadcaster_id": channel_id
        }
        responses: List[bool] = []
        async with aiohttp.ClientSession() as session:
            for r in rewards:
                site = await session.post(
                    "https://api.twitch.tv/helix/channel_points/custom_rewards",
                    params=params, json=r, headers=headers,
                )
                data = await site.json()
                try:
                    data['data'][0]['id']
                    responses.append(True)
                except KeyError:
                    allowed_error = "CREATE_CUSTOM_REWARD_DUPLICATE_REWARD"
                    responses.append(data['message'] == allowed_error)
        return all(responses)

    async def delete_rewards(
            self,
            token: Optional[str],
            channel_id: str,
            rewards: List[ChannelPointsRewardCreatePayload]) -> None:
        """
        Create the "change headphone colour" reward.
        """

        headers = {
            "Authorization": f"Bearer {token or self.access_token}",
            "Client-Id": self.client_id,
        }
        params = {
            "broadcaster_id": channel_id,
            "only_manageable_rewards": "true",
        }
        async with aiohttp.ClientSession() as session:

            # Get the current rewards
            site = await session.get(
                "https://api.twitch.tv/helix/channel_points/custom_rewards",
                params=params, headers=headers,
            )
            data: List[ChannelPointsRewardPayload] = (await site.json())['data']

            # Get the IDs of rewards that match with the ones we want to disable
            current_reward_names = [r['title'] for r in rewards]
            ids = [
                d['id']
                for d in data
                if d['title'] in current_reward_names
            ]

            # Disable them
            for id in ids:
                params = {
                    "broadcaster_id": channel_id,
                    "id": id,
                }
                site = await session.delete(
                    "https://api.twitch.tv/helix/channel_points/custom_rewards",
                    # params=params, json={"is_enabled": False}, headers=headers,
                    params=params, headers=headers,
                )

    async def is_subscriber(
            self,
            token: Optional[str],
            channel_id: str,
            user_id: str) -> bool:
        """
        Returns whether or not a given user is a subscriber.
        """

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {token or self.access_token}",
                "Client-Id": self.client_id,
            }
            params = {
                "broadcaster_id": channel_id,
                "user_id": user_id,
            }
            url = "https://api.twitch.tv/helix/subscriptions"
            site = await session.get(url, params=params, headers=headers)
        try:
            (await site.json())['data'][0]
        except (KeyError, IndexError):
            return False
        return True

    async def update_redemption_status(
            self,
            token: Optional[str],
            redemption_id: str,
            channel_id: str,
            reward_id: str,
            status: RewardRedemptionStatus):
        """
        Update the redemption with the given ID.
        """

        headers = {
            "Authorization": f"Bearer {token or self.access_token}",
            "Client-Id": self.client_id,
        }
        params = {
            "id": redemption_id,
            "broadcaster_id": channel_id,
            "reward_id": reward_id,
        }
        json = {
            "status": status,
        }
        log.info(f"Setting redemption with ID {redemption_id} to {status}")
        async with aiohttp.ClientSession() as session:
            await session.patch(
                (
                    "https://api.twitch.tv/helix/"
                    "channel_points/custom_rewards/redemptions"
                ),
                params=params, json=json, headers=headers,
            )


class TwitchConnector:
    """
    An object to handle the Twitch pubsub websocket.
    """

    def __init__(self, access_token: str, channel_id: str, channel_name: str):
        self.access_token: str = access_token
        self.channel_id: str = channel_id
        self.channel_name: str = channel_name

        self.heartbeat_task: Optional[asyncio.Task] = None
        self.message_task: Optional[asyncio.Task] = None
        self.irc_message_task: Optional[asyncio.Task] = None

        self.socket: Optional[WebSocketClientProtocol] = None
        self.chat_socket: Optional[WebSocketClientProtocol] = None

        self.message_queue = asyncio.Queue[ChannelPointsEventMessage]()
        self.chat_queue = asyncio.Queue[Tuple[TwitchChatter, str]]()

        self.chat_handlers: list = []
        self.reward_handlers: list = []

    async def handle_message_receive(self):
        """
        Handle receiving and distributing the messages from the websocket.
        """

        while True:
            try:
                data_raw = await self.socket.recv()  # type: ignore
            except Exception as e:
                log.error(f"Hit error reading socket - {e}")
                continue
            data = json.loads(data_raw)
            if data['type'] == "PONG":
                log.debug("Pong received")
            elif data['type'] == "MESSAGE" and data['data']['topic'].startswith("channel-points-channel-v1"):
                log.debug("Reward redeem message received")
                self.message_queue.put_nowait(json.loads(data['data']['message']))
            else:
                log.debug(f"Data received - {data}")

    async def send_channel_listen(self):
        """
        Basic setup for the client - tell Twitch that we want to hear
        channel point redemptions.
        """

        data = json.dumps({
            "type": "LISTEN",
            "data": {
                "topics": [
                    f"channel-points-channel-v1.{self.channel_id}",
                ],
                "auth_token": self.access_token,
            }
        })
        await self.socket.send(data)  # type: ignore

    async def run(self):
        """
        Connect the websocket, set up what we're listening to, handle pings,
        and handle messages.
        """

        # Connect to pubsub
        log.info("Connecting to pubsub...")
        self.socket = await websockets.connect("wss://pubsub-edge.twitch.tv")  # type: ignore

        # Connect to IRC
        log.info("Connecting to IRC...")
        self.chat_socket = await websockets.connect("wss://irc-ws.chat.twitch.tv:443")  # type: ignore

        # Done
        log.info("Connected")

        # Start tasks for pubsub
        log.info("Starting pubsub heartbeat")
        self.heartbeat_task = asyncio.create_task(self.send_ping())
        log.info("Sending pubsub listen payload")
        await self.send_channel_listen()
        log.info("Starting pubsub message receive task")
        self.message_task = asyncio.create_task(self.handle_message_receive())

        # Start tasks for IRC
        log.info("Sending IRC pass and nick data")
        await self.chat_socket.send(f"PASS oauth:{self.access_token}")
        await self.chat_socket.send(f"NICK {self.channel_name}")
        self.irc_message_task = asyncio.create_task(self.handle_irc_message_receive())

    async def cleanup(self):
        """
        Cancel the running tasks and close the websocket connection.
        """

        log.info("Cancelling tasks")
        self.heartbeat_task.cancel()  # type: ignore
        self.message_task.cancel()  # type: ignore
        self.irc_message_task.cancel()  # type: ignore
        log.info("Closing websocket")
        await self.socket.close()  # type: ignore
        await self.chat_socket.close()  # type: ignore

    async def send_ping(self):
        """
        Send pings to the Twitch websocket so we don't get disconnected.
        """

        while True:
            log.debug("Ping sent...")
            data = json.dumps({"type": "PING"})
            await self.socket.send(data)  # type: ignore
            await asyncio.sleep(60 * 1)

    async def send_message(self, content: str):
        """
        Send pings to the Twitch websocket so we don't get disconnected.
        """

        log.debug("Sending message: %s", content)
        await self.chat_socket.send(  # type: ignore
            f"PRIVMSG #{self.channel_name} :{content}"
        )

    async def handle_irc_message_receive(self):
        """
        Handle the receiving of messages from Twitch by IRC. This will only
        need to be pings and the "yea you're connected" message.
        """

        # Wait for our "ok"
        log.info("Waiting for an 'ok' from Twitch for IRC...")
        waiting_for_ok: bool = True
        while waiting_for_ok:

            # Read messages
            try:
                data_raw: str = await self.chat_socket.recv()  # type: ignore
            except Exception as e:
                log.error(f"Hit error reading socket - {e}")
                continue

            # Split by line
            for line in data_raw.split("\r\n"):

                # Login failed message
                if line == ":tmi.twitch.tv NOTICE * :Login unsuccessful":
                    log.error("Failed to connect to IRC - login failed")
                    try:
                        assert self.chat_socket
                        await self.chat_socket.close()
                    except AssertionError:
                        pass
                    return

                # Login succeed message
                elif line.endswith(":Welcome, GLHF!"):
                    log.info("Connected properly to IRC")
                    waiting_for_ok = False
                    break

        # Join the chatroom and request tags
        log.info(f"Joining channel {self.channel_name}")
        assert self.chat_socket
        await self.chat_socket.send(f"JOIN #{self.channel_name}")
        await self.chat_socket.send(f"CAP REQ :twitch.tv/tags")

        # And now handle pings
        while True:

            # Read messages
            try:
                data_raw: str = await self.chat_socket.recv()  # type: ignore
            except Exception as e:
                log.error(f"Hit error reading socket - {e}")
                continue

            # Split by line
            for line in data_raw.split("\r\n"):

                # Blank message
                if not line.strip():
                    continue

                # Ping message
                elif line.startswith("PING "):
                    log.info("Sending IRC PONG")
                    await self.chat_socket.send(f"PONG {line.split(' ', 1)[1]}")

                # Text message
                elif (match := TEXT_MESSAGE_REGEX.match(line)):
                    log.debug("Adding text to chat queue: %s" % match.group("message"))
                    if match.group("tags"):
                        self.chat_queue.put_nowait(
                            (
                                TwitchChatter.parse(
                                    match.group("username"),
                                    match.group("tags"),
                                ),
                                match.group("message"),
                            ),
                        )
                    else:
                        self.chat_queue.put_nowait(
                            (
                                TwitchChatter(match.group("username")),
                                match.group("message"),
                            ),
                        )

                # Elsey
                else:
                    log.info(f"IRC message received: {line}")

