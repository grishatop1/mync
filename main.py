import os
import sys
import threading

from client.gui import MainApplication
from client.client import Client
from client.cachemngr import CacheManager
from client.player import Player

class Controller:
    def __init__(self) -> None:
        self.gui = None
        self.client = None
        self.cache = CacheManager()
        self.player = Player(self)

    def runGUI(self):
        self.gui = MainApplication(self)
        self.gui.mainloop()

    def createClientInstance(self, ip, port, username):
        self.client = Client(self, ip, port, username)
        result = self.client.connect()
        if result == True:
            self.writeToCache("ip", f"{ip}:{port}")
            self.writeToCache("username", username)
            self.gui.connect_frame.setConnectedState(dialog=True)
        elif result == "badusername":
            self.client = None
            self.gui.connect_frame.setNormalState()
            self.gui.showDialog("Username already taken.", "Connection", "warning")
        else:
            self.client = None
            self.gui.connect_frame.setNormalState()
            self.gui.showDialog("Couldn't connect.", "Connection", "warning")
    
    def removeClientInstance(self):
        self.resetAll()
        self.client.disconnect()
        self.client = None

    def lostClientConnection(self):
        self.removeClientInstance()
        self.gui.connect_frame.setNormalState()
        self.gui.showDialog("Connection lost.", "Connection", "warning")

    def isClientAlive(self):
        if self.client: return True

    def writeToCache(self, key, value):
        self.cache.write(key, value)

    def getFromCache(self, key):
        return self.cache.read(key)

    def sendMessage(self, message):
        if self.client:
            self.client.transmitMsg(
                message,
                "blue"
            )
        else:
            self.gui.log_frame.insertTextLine(
                f"[Offline]: {message}"
            )

    def recvMessage(self, message):
        self.gui.log_frame.insertTextLine(
            message,
            "blue"
        )

    def requestTracksForReq(self):
        if self.client:
            self.client.getTracks()

    def loadTracksForReq(self, tracks):
        self.gui.top.loadTracksInReq(tracks)

    def addUsers(self, users):
        self.gui.connections_frame.addUsers(users)

    def addUser(self, user):
        self.gui.connections_frame.addUser(user)

    def removeUser(self, user):
        self.gui.connections_frame.removeUser(user)

    def sendPlaytrackRequest(self, songname):
        threading.Thread(target=self.client.reqSong, args=(songname,), daemon=True).start()

    def getCacheMusic(self):
        return os.listdir(self.cache.sharedmusic)

    def startSongRequesting(self, songname):
        self.gui.log_frame.upload_btn["state"] = "disabled"
        self.gui.log("Missing song! Requesting it...", "red")
        self.gui.netstatus_label.set(f"[0%] Downloading {songname[:70]}")
        self.gui.top.closeRequestWindow()

        threading.Thread(target=self.client.downloadSong, args=(songname,), daemon=True).start()

    def readyForTheSong(self, songname):
        self.gui.log(
            "Ready for the next song! Waiting for others..."
        )
        self.gui.top.closeRequestWindow()

    def playTrack(self, songname, time_time, start):
        self.gui.player_frame.resetState()
        songpath = self.cache.sharedmusic + songname
        try:
            self.player.playTrack(
                songpath,
                songname,
                start
            )
        except:
            self.gui.log("Can't play this track, sorry.", "red")
            return

        self.gui.player_frame.setPlayingState(songname[:70]+"...")
        self.gui.log("Playing next track!", "green")

    def stopTrack(self):
        self.player.stopTrack()
        self.gui.player_frame.resetState()

    def updateDownloadStatus(self, songname, percent):
        self.gui.netstatus_label.set(f"[{percent}%] Downloading {songname[:70]}")

    def downloadSuccess(self):
        self.gui.netstatus_label.reset()
        self.gui.log_frame.upload_btn["state"] = "normal"
        self.gui.log("Song has been downloaded, waiting for others!", "green")

    def downloadFail(self):
        self.gui.netstatus_label.reset()
        self.gui.log_frame.upload_btn["state"] = "normal"
        self.gui.log("Download failed.", "red")
        self.gui.showDialog(
            "Failed to download the song :(",
            "File Transfer", "warning"
        )

    def resetAll(self):
        self.stopTrack()

        self.gui.connect_frame.setNormalState()
        self.gui.log_frame.clearLogs()
        self.gui.log_frame.upload_btn.configure(text="Upload", state="normal")
        self.gui.connections_frame.clear()
        self.gui.player_frame.status_label["text"] = "Waiting for the track..."

        self.gui.focus()

if __name__ == "__main__":
    if sys.platform != "win32" and sys.platform != "win64":
        print("Mync client supports only windows for now :/")
        sys.exit()

    controller = Controller()
    controller.runGUI()