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
        self.gui.resetAll()
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

if __name__ == "__main__":
    if sys.platform != "win32" and sys.platform != "win64":
        print("Mync client supports only windows for now :/")
        sys.exit()

    controller = Controller()
    controller.runGUI()