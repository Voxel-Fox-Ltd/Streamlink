from __future__ import annotations

import random
import argparse

import win32com.client


parser = argparse.ArgumentParser()
parser.add_argument(
    "message",
    nargs="?",
    help="The message that you want said by the TTS.",
)
parser.add_argument(
    "--voice",
    required=False,
    help="The voice that you want to run the TTS. Must be an exact match, case sensitive.",
)
parser.add_argument(
    "--voice-like",
    required=False,
    help=(
        "The voice that you want to run the TTS. Can be a partial match with an existing voice. "
        "Case sensitive. Ignored if '--voice' is supplied."
    ),
)
parser.add_argument(
    "--random-voice",
    action="store_true",
    required=False,
    help=(
        "The voice that you want to run the TTS. Can be a partial match with an existing voice. "
        "Case sensitive. Ignored if '--voice' or '--voicelike' is supplied."
    ),
)
parser.add_argument(
    "--list-voices",
    action="store_true",
    required=False,
    help="Lists all of the available voices.",
)


def run_tts(message: str, voice: str = None, *, list_voices: bool = False) -> None:
    """
    Handle a user on Twitch redeeming a run TTS reward
    """

    # Get the client
    sapi = win32com.client.Dispatch("SAPI.SpVoice")

    # Get the voices
    cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
    cat.SetID("HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech_OneCore\\Voices", False)
    voice_list = list(cat.EnumerateTokens())
    cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
    cat.SetID("HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices", False)
    voice_list += list(cat.EnumerateTokens())

    # See if they want to list them
    if list_voices:
        print("\n".join([i.GetAttribute("Name") for i in voice_list]))
        return

    # Get what we're lookin for
    if voice == "%":
        v = random.choice(voice_list)
    elif voice and voice.startswith("%"):
        try:
            v = [i for i in voice_list if voice[1:] in i.GetAttribute("Name")][0]
        except IndexError:
            raise RuntimeError(f"Failed to get a voice matching '{voice[1:]}'")
    elif voice:
        try:
            v = [i for i in voice_list if voice == i.GetAttribute("Name")][0]
        except IndexError:
            raise RuntimeError(f"Failed to get a voice matching '{voice}'")
    else:
        v = None

    # Speak the voice
    old_voice = sapi.Voice
    if v:
        sapi.Voice = v
    sapi.Speak(message)
    if v:
        sapi.Voice = old_voice


if __name__ == "__main__":
    args = parser.parse_args()
    if args.list_voices:
        run_tts(None, list_voices=True)  # type: ignore
    else:
        voice = args.voice
        if not voice and args.voice_like:
            voice = f"%{args.voice_like}"
        if not voice and args.random_voice:
            voice = "%"
        run_tts(args.message, voice)
