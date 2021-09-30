import os
import pickle
import socket
import threading

from modules.transfer import Transfer
from modules.ft import ClientFT

class Client:
    def __init__(self, controller, ip, port, username):
        self.controller = controller
        self.s = socket.socket()

        self.ip = ip
        self.port = port
        self.addr = (ip,port)
        self.username = username

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

        self.s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        self.t = Transfer(self.s)
        self.t.send(self.username.encode())
        connections = self.t.recvData()
        if connections == b"usernametaken":
            return "badusername"
        try:
            users = pickle.loads(connections)
        except:
            return

        self.controller.net.addUser(self.username)
        self.controller.net.addUsers(users)

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
            data = self.t.recvData()
            if not data or data == b"drop":
                break

            data = pickle.loads(data)

            if data["method"] == "play":
                play_at = data["play_at"]
                songname = data["songname"]
                starttime = data["starttime"]
                try:
                    self.app.player_frame.playTrack(songname, play_at, starttime)
                    self.app.log(f"Playing {songname}", "green")
                except:pass
                continue

            elif data["method"] == "returnTracks":
                if self.app.log_frame.req_win:
                    self.app.log_frame.req_win.loadTracks(data["data"])

            elif data["method"] == "checksong":
                songname = data["songname"]
                songsize = data["songsize"] #used if client has not track
                tracks = os.listdir(self.app.cache.sharedmusic)
                if not songname in tracks:
                    self.app.log_frame.upload_btn["state"] = "disabled"
                    self.app.log("Missing song! Requesting it...", "red")
                    self.app.setStatusLabel(f"Downloading {songname}")
                    threading.Thread(
                        target=self.downloadSong, 
                        daemon=True,
                        args=(songname,songsize)
                        ).start()
                else:
                    self.t.sendDataPickle(
                        {"method": "ready", "songname": songname}
                    )
                    self.app.log(
                        "Ready for the next song! Waiting for others...")

            elif data["method"] == "connectionplus":
                self.controller.net.addUser(data["user"])

            elif data["method"] == "connectionminus":
                self.controller.net.removeUser(data["user"])

            elif data["method"] == "transmit":
                self.controller.net.recvMessage(data["message"])

            elif data["method"] == "echo":
                message = f"[You]: {data['msg']}"
                self.controller.net.recvMessage(message)

            elif data["method"] == "in-mute":
                self.app.connections_frame.renameUser(
                    data["user"],
                    data["user"] + " (muted)"
                )

            elif data["method"] == "in-outmute":
                self.app.connections_frame.renameUser(
                    data["user"] + " (muted)",
                    data["user"]
                )

        if not self.force_disconnect:
            self.alive = False
            self.s.close()
            self.controller.lostClientConnection()

    def uploadSong(self, path):
        self.ft = ClientFT(self, self.ip, self.port+1)
        if self.ft.connect():
            self.ft.upload(path)
        self.ft = None

    def downloadSong(self, songname, songsize):
        self.ft = ClientFT(self, self.ip, self.port+1)
        if self.ft.connect():
            if self.ft.download(songname, songsize):
                self.t.sendDataPickle(
                    {"method":"ready"}
                )
                self.app.resetStatusLabel()
                self.app.log("Ready for the song!\nWaiting for others...", "green")

            self.app.log_frame.upload_btn["state"] = "normal"
        self.ft = None

    def getTracks(self):
        self.t.sendDataPickle({"method":"gettracks"})

    def reqSong(self, songname):
        self.t.sendDataPickle({"method": "req", "songname": songname},
                              blocking=False)

    def transmitMsg(self, message, color="black"):
        self.t.sendDataPickle({"method":"transmit", "message":message,
                               "color": color}, blocking=False)

    def transmitMuted(self, muted):
        if muted:
            self.t.sendDataPickle(
                {"method": "im-muted"}
            )
        else:
            self.t.sendDataPickle(
                {"method": "im-unmuted"}
            )