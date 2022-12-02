# Streamlink

VX Streamlink is a simple Python application to link to your Twitch chat. It
reads your chat, gives your viewers a voice, and then uses a simple VLC media
player integration to play their messages aloud directly into your ears.

Also featured is an inbuilt config system, which allows you to override the
voices that given people have; do simple (and complex) word replacements to help
out the TTS (eg "ppl" -> "people", "idk" -> "I don't know"); set up limits to
limit how many words will be said per message; etc.

# Usage

* Install VLC media player (32 bit).
* Install the Python requirements (`pip install -r requirements.txt`).
* Set up and/or modify your `config.toml` file.
* Run the `streamlink.py` file.

Running the `streamlink.py` file will automatically open your browser to get a
Twitch oauth token so as to be able to connect to your chat.
