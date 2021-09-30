import os
import sys
import threading

from client.gui import MainApplication
from client.client import Client
from client.cachemngr import CacheManager
from client.player import Player

class NetController:
    def __init__(self, controller) -> None:
        self.controller = controller

    def sendMessage(self, message):
        if self.controller.client:
            self.controller.client.transmitMsg(
                message,
                "blue"
            )
        else:
            self.controller.gui.log_frame.insertTextLine(
                f"[Offline]: {message}"
            )

    def recvMessage(self, message):
        self.controller.gui.log_frame.insertTextLine(
            message,
            "blue"
        )

    def addUsers(self, users):
        self.controller.gui.connections_frame.addUsers(users)

    def addUser(self, user):
        self.controller.gui.connections_frame.addUser(user)

    def removeUser(self, user):
        self.controller.gui.connections_frame.removeUser(user)

class Controller:
    def __init__(self) -> None:
        self.gui = None
        self.client = None
        self.cache = CacheManager()
        self.player = Player(self)

        self.net = NetController(self)

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

    def writeToCache(self, key, value):
        self.cache.write(key, value)

    def getFromCache(self, key):
        return self.cache.read(key)

if __name__ == "__main__":
    if sys.platform != "win32" and sys.platform != "win64":
        print("Mync client supports only windows for now :/")
        sys.exit()

    controller = Controller()
    controller.runGUI()