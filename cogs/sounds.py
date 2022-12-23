from typing import Optional
import pathlib
import logging

import vlc

from . import utils


log = logging.getLogger("streamlink.cogs.sounds")


async def handle_redemption(
        twitch: utils.TwitchConnector,
        oauth: utils.TwitchOauth,
        redemption: utils.types.ChannelPointsRedemption) -> Optional[bool]:
    """
    Allow sounds to be played from Twitch redemptions.
    """

    # Onto Twitch channel point redemptions
    # Get the title of the reward
    reward_title = redemption['reward']['title']

    # Check if it's something we care about
    if not reward_title.startswith("Play sound: "):
        return None

    # Get the path to the file we want to play
    root = pathlib.Path()

    # Try and play it via VLC
    try:
        partial = "sounds/" + reward_title[len("Play sound: "):] + ".wav"
        filename = (root / partial).resolve()
        vlc_instance: vlc.Instance = vlc.Instance()
        vlc_player: vlc.MediaPlayer = vlc_instance.media_player_new()
        vlc_media: vlc.Media = vlc_instance.media_new(filename)
        vlc_player.set_media(vlc_media)
        vlc_player.audio_output_device_set(
            None,
            utils.get_sound_output_id(twitch),
        )
        vlc_player.play()
        log.info("Playing sound file: %s", filename)
        return True
    except Exception as e:
        log.error("Error playing sound file", exc_info=e)
        return False
