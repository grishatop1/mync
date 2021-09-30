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
            self.gui.connect_frame.setConnectedState(dialog=True)
        elif result == "badusername":
            self.gui.connect_frame.setNormalState()
            self.gui.showDialog("Username already taken.", "Connection", "warning")
        else:
            self.gui.connect_frame.setNormalState()
            self.gui.showDialog("Couldn't connect.", "Connection", "warning")
    
    def removeClientInstance(self):
        self.client.disconnect()
        self.client = None

    def lostClientConnection(self):
        self.gui.connect_frame.setNormalState()
        self.gui.showDialog("Connection lost.", "Connection", "warning")
        self.client = None

if __name__ == "__main__":
    if sys.platform != "win32" and sys.platform != "win64":
        print("Mync client supports only windows for now :/")
        sys.exit()

    controller = Controller()
    controller.runGUI()