# mync

**mync** - Python radio station app

Listen to music together in sync! Request from server's songlist or upload your own songs.

## Requirements
**mync** requires **pygame** (at least 2.0.0) because it uses pygame's mixer module for playing audio. **ttkbootstrap** is used for the stylised interface.

Run the following commands in your CLI to get the requirements.

`pip install pygame`

`pip install ttkbootstrap`

If you're running **server** then you need:

`pip install requests`

`pip install beautifulsoup4`

## Usage
In order to serve music as server, you need to copy your .mp3 files to the `servermusic` folder, and then run `server.py`. Share the IP from the console with your friends.

If someone else is hosting the server, just run `main.py` to launch the GUI client window. Choose a username and input the IP your server host gave you.

Have fun!
