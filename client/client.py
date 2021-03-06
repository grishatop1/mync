import os
import pickle
import socket
import threading

from modules.transfer import Transfer
from modules.ft import ClientFT

from shutil import copy

class Client:
    def __init__(self, controller, ip, port, username):
        self.controller = controller
        self.s = socket.socket()

        self.ip = ip
        self.port = port
        self.addr = (ip,port)
        self.username = username

        self.ft_addr = None
        self.ft = None

        self.force_disconnect = False
        self.alive = False
    
    def connect(self):
        try:
            self.s.settimeout(5)
            self.s.connect(self.addr)
            self.alive = True
        except socket.error:
            return
        except Exception as e:
            print(e)
            return

        #self.s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        self.t = Transfer(self.s)
        self.t.send(self.username.encode())

        response = self.t.recvData()
        if response == b"badusername":
            return "badusername"
        try:
            data = pickle.loads(response)
            connections = data["connections"]
            self.ft_addr = (self.ip, data["ft-port"])
        except:
            return

        self.controller.addUsers(connections)
        self.controller.addUser(self.username)

        self.t.send(b"gotall")
        self.s.settimeout(None)
        threading.Thread(target=self.mainThread, daemon=True).start()
        return True

    def disconnect(self):
        if not self.alive: return
        self.force_disconnect = True
        self.alive = False
        self.t.send(b"drop")
        self.s.close()

    def mainThread(self):
        while self.alive:
            response = self.t.recvData()
            if not response or response == b"drop":
                break

            data = pickle.loads(response)

            if data["method"] == "play":
                play_at = data["play_at"]
                songname = data["songname"]
                starttime = data["starttime"]
                self.controller.playTrack(songname, play_at, starttime)

            elif data["method"] == "stop":
                self.controller.stopTrack()

            elif data["method"] == "returnTracks":
                self.controller.loadTracksForReq(data["data"])

            elif data["method"] == "checksong":
                songname = data["songname"]
                tracks = self.controller.getCacheMusic()
                if not songname in tracks:
                    self.controller.startSongRequesting(songname)
                else:
                    self.sendReady()
                    self.controller.readyForTheSong(songname)

            elif data["method"] == "connectionplus":
                self.controller.addUser(data["user"])

            elif data["method"] == "connectionminus":
                self.controller.removeUser(data["user"])

            elif data["method"] == "set-suffix":
                self.controller.userSuffix(
                    data["username"], data["suffix"]
                )

            elif data["method"] == "server-msg":
                self.controller.recvServerMessage(
                    data["msg_id"], 
                    data["color"],
                    data["args"]
                )

            elif data["method"] == "client-msg":
                self.controller.recvUserMessage(data["message"], data["sender"])

            elif data["method"] == "echo":
                message = f"[You]: {data['msg']}"
                self.controller.log(message, "black")

        if not self.force_disconnect:
            self.alive = False
            self.s.close()
            self.controller.lostClientConnection()

    def uploadSong(self, songpath):
        songname = os.path.basename(songpath)
        copy(
            songpath, 
            self.controller.cache.sharedmusic + songname
        )
        
        self.ft = ClientFT(self, *self.ft_addr)
        if self.ft.createConnection():
            self.ft.uploadThread(songpath)
        else:
            self.controller.uploadFail()

    def downloadSong(self, songname):
        self.ft = ClientFT(self, *self.ft_addr)
        if self.ft.createConnection():
            self.ft.downloadThread(songname)
        else:
            self.controller.downloadFail()

    def getTracks(self):
        self.t.sendDataPickle({"method":"gettracks"})

    def reqSong(self, songname):
        self.t.sendDataPickle({"method": "req", "songname": songname},
                              blocking=False)

    def reqYoutube(self, link):
        self.t.sendDataPickle(
            {"method": "req-yt", "link": link}
        )

    def sendReady(self):
        self.t.sendDataPickle(
            {"method": "ready"}
        )

    def transmitMsg(self, message, color="black"):
        self.t.sendDataPickle({"method":"transmit", "message":message,
                               "color": color}, blocking=False)

    def transmitSuffix(self, sfx):
        self.t.sendDataPickle(
            {"method": "suffix", "suffix": sfx}
        )

    def transmitCommand(self, cmd, content):
        self.t.sendDataPickle(
            {"method": "command", "cmd": cmd, "content":content}
        )