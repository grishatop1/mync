from pygame import mixer

class Player:
    def __init__(self, controller) -> None:
        self.controller = controller
        mixer.init()

        self.playing = None

    def playTrack(self, path, songname, start_time=0):
        mixer.music.load(path)
        mixer.music.play(start=start_time)
        self.playing = songname

    def stopTrack(self):
        mixer.music.stop()
        self.playing = None

    def setVolume(self, value):
        volume = value/100
        mixer.music.set_volume(volume)