import os
import sys
import time
import threading
import multiprocessing

from client.gui import MainApplication
from client.client import Client
from client.cachemngr import CacheManager
from client.player import Player
from client.presence import MyncPresence

from modules.langs import LanguageSupport
from modules.utils import youtube_url_validation

class Controller:
    def __init__(self) -> None:
        self.gui = None
        self.client = None
        self.cache = CacheManager()
        self.player = Player(self)
        self.lng = LanguageSupport(self, "languages.json")
        self.ds = MyncPresence(self, os.getpid())

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
            self.ds.setConnected()
        elif result == "badusername":
            self.client = None
            self.gui.connect_frame.setNormalState()
            self.gui.showDialog(self.lng("conn_err_alreadytaken"), "Connection", "warning")
        else:
            self.client = None
            self.gui.connect_frame.setNormalState()
            self.gui.showDialog(self.lng("conn_err_couldnt"), "Connection", "warning")
    
    def removeClientInstance(self):
        self.resetAll()
        self.client.disconnect()
        self.client = None

    def lostClientConnection(self):
        self.removeClientInstance()
        self.gui.connect_frame.setNormalState()
        self.gui.showDialog(self.lng("conn_err_lost"), "Connection", "warning")

    def isClientAlive(self):
        if self.client: return True

    def writeToCache(self, key, value):
        self.cache.write(key, value)

    def getFromCache(self, key):
        return self.cache.read(key)

    def sendMessage(self, message):
        if self.client:
            if youtube_url_validation(message):
                self.gui.log(self.lng("logs_yt_accepted"))
                self.client.reqYoutube(message)
                return
            self.client.transmitMsg(
                message,
                "blue"
            )
        else:
            self.gui.log_frame.insertTextLine(
                self.lng("logs_offline_msg", message)
            )

    def recvMessage(self, message, color):
        self.gui.log_frame.insertTextLine(
            message,
            color
        )

    def requestTracksForReq(self):
        if self.client:
            self.client.getTracks()

    def loadTracksForReq(self, tracks):
        self.gui.top.loadTracksInReq(tracks)

    def addUsers(self, users):
        self.gui.connections_frame.addUsers(users)

    def addUser(self, user):
        self.gui.log(self.lng("logs_user_joined", user), "#d97000")
        self.gui.connections_frame.addUser(user)

    def removeUser(self, user):
        self.gui.log(self.lng("logs_user_left", user), "#d97000")
        self.gui.connections_frame.removeUser(user)

    def userSuffix(self, user, sfx):
        self.gui.connections_frame.changeSuffix(user, sfx)

    def transmitSuffix(self, sfx):
        if self.client:
            self.client.transmitSuffix(sfx)

    def sendPlaytrackRequest(self, songname):
        threading.Thread(target=self.client.reqSong, args=(songname,), daemon=True).start()

    def getCacheMusic(self):
        return os.listdir(self.cache.sharedmusic)

    def readyForTheSong(self, songname):
        self.gui.log(
            self.lng("logs_track_ready")
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
            self.gui.log(self.lng("logs_cant_play"), "red")
            return

        self.gui.player_frame.setPlayingState(songname[:70]+"...")
        self.gui.log(self.lng("logs_playing_now"), "green")
        self.ds.setPlaying(songname, time.time())

    def stopTrack(self):
        self.player.stopTrack()
        self.gui.player_frame.resetState()

    def startSongRequesting(self, songname):
        self.gui.log_frame.upload_btn["state"] = "disabled"
        self.gui.log(self.lng("logs_requesting"), "red")
        self.gui.netstatus_label.set(self.lng("netw_downloading", "0%", songname))
        self.gui.top.closeRequestWindow()

        if self.client.ft and self.client.ft.running:
            self.client.ft.kill()

        threading.Thread(target=self.client.downloadSong, args=(songname,), daemon=True).start()

    def downloadSuccess(self):
        self.gui.netstatus_label.reset()
        self.gui.log_frame.upload_btn["state"] = "normal"
        self.gui.log(self.lng("logs_downloaded"), "green")

    def downloadFail(self):
        self.gui.netstatus_label.reset()
        self.gui.log_frame.upload_btn["state"] = "normal"
        self.gui.log(self.lng("logs_dl_failed"), "red")

    def cancelDownload(self):
        if self.client.ft:
            self.client.ft.kill(fail=True)

    def updateDownloadStatus(self, songname, percent):
        self.gui.netstatus_label.set(
            self.lng("netw_downloading", f"{percent}%", songname)
        )

    def startUploading(self, songpath):
        self.gui.log_frame.upload_btn["state"] = "disabled"
        self.gui.log(self.lng("logs_uploading"))
        self.gui.netstatus_label.set(self.lng("netw_uploading"))

        threading.Thread(target=self.client.uploadSong, args=(songpath,), daemon=True).start()

    def uploadSuccess(self):
        self.gui.top.closeUploadWindow()
        self.gui.netstatus_label.reset()
        self.gui.log_frame.upload_btn["state"] = "normal"
        self.gui.log(self.lng("logs_uploaded"), "green")

    def uploadFail(self):
        self.closeUpload()
        self.gui.log(self.lng("logs_upload_failed"), "red")

    def updateUploadStatus(self, bps, recvd):
        try:
            if self.gui.top.upload_win:
                self.gui.top.upload_win.updateStatus(bps, recvd)
        except: pass

    def closeUpload(self):
        self.gui.top.closeUploadWindow()
        self.gui.netstatus_label.reset()
        self.gui.log_frame.upload_btn["state"] = "normal"

    def cancelUpload(self):
        self.closeUpload()
        if self.client.ft:
            self.client.ft.kill()
        self.gui.log(self.lng("logs_upload_canceled"), "red")

    def resetAll(self):
        self.stopTrack()
        self.cancelUpload()
        self.cancelDownload()

        self.gui.connect_frame.setNormalState()
        self.gui.log_frame.clearLogs()
        self.gui.log_frame.upload_btn.configure(text="Upload", state="normal")
        self.gui.connections_frame.clear()
        self.gui.player_frame.resetState()

        self.gui.focus()

if __name__ == "__main__":
    if sys.platform != "win32" and sys.platform != "win64":
        print("Mync client supports only windows for now :/")
        sys.exit()

    multiprocessing.freeze_support() #for pyinstaller
    controller = Controller()
    controller.runGUI()