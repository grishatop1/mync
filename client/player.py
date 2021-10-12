from pygame import mixer

class Player:
    def __init__(self, controller) -> None:
        self.controller = controller
        mixer.init()
        self.playing = None
        self.loaded = False

    def loadCacheVolume(self):
        volume = self.controller.getFromCache("volume")
        self.last_volume = volume
        self.loaded = True
        return volume

    def playTrack(self, path, songname, start_time=0):
        mixer.music.load(path)
        mixer.music.play(start=start_time)
        self.playing = songname

    def stopTrack(self):
        mixer.music.stop()
        self.playing = None

    def setVolume(self, volume):
        pyvolume = volume/100
        mixer.music.set_volume(pyvolume)
        if volume == 0:
            self.controller.writeToCache("volume", 20)
        else:
            self.controller.writeToCache("volume", volume)

        if volume == 0 and self.last_volume > 0:
            self.controller.transmitSuffix(" (muted)")
        elif self.last_volume == 0 and volume > 0:
            self.controller.transmitSuffix("")

        self.last_volume = volume