import pickle
import socket
import threading
import os
import time
from typing import SupportsComplex

from modules.transfer import Transfer
from shutil import move as moveFile

SONG_PATH = "servermusic/"
UPLOAD_PATH = "servermusic/upload/"

class ServerFT:
    def __init__(self, server, ip, port):
        self.server = server
        self.ip = ip
        self.port = port
        self.addr = (ip,port)

        self.connections = {}

        self.s = socket.socket()
        self.s.bind(self.addr)
        self.s.listen()

        threading.Thread(target=self.acceptThread, daemon=True).start()
        print(f"File transfer server started on {self.addr[0]}:{self.addr[1]}")

    def acceptThread(self):
        while True:
            conn, addr = self.s.accept()
            threading.Thread(target=self.clientHandler, args=(conn,addr),daemon=True).start()

    def clientHandler(self, conn, addr):
        conn.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        t = Transfer(conn)
        username = t.recvData().decode()
        if not username in self.server.connections:
            t.send(b"badusername")
            return
        client = self.server.connections[username]
        t.send(b"gotall")

        response = t.recvData()
        data = pickle.loads(response)
        if data["method"] == "upload":
            songname, songsize = data["songname"], data["songsize"]
            client.songhandler = SongHandler(self.server, t, username, songname, songsize)

            while True:
                data = t.recvData()
                if not data or data == b"drop":
                    break
                client.songhandler.write(data)

        elif data["method"] == "download":
            self.server.transmitAllExceptMe(
                f"{username} is downloading...",
                "blue",
                username    
            )
            songname = data["songname"]
            songpath = "servermusic/" + songname
            with open(songpath, "rb") as f:
                while True:
                    data = f.read(1024*4)
                    if not data: break
                    try:
                        t.send(data)
                    except:
                        break
            try:
                response = t.recvData()
            except:
                pass
        
        conn.shutdown(2)
        conn.close()

class SongReceiver:
    def __init__(self, songpath, songname, songsize) -> None:
        self.songname = songname
        self.songpath = songpath
        self.songsize = songsize
        
        self.recvd = 0
        self.f = open(self.songpath, "ab")
        self.closed = False

    def write(self, data):
        try:
            self.f.write(data)
        except:
            self.close()
            return
        
        self.recvd += len(data)

        if self.recvd == self.songsize:
            return True

    def getPercent(self):
        percent = round((self.recvd/self.songsize)*100, 1)
        return percent

    def close(self):
        self.closed = True
        self.f.close()

class ClientFT:
    def __init__(self, client, ip, port) -> None:
        self.client = client
        self.ip = ip
        self.port = port
        self.addr = (ip,port)
        self.s = socket.socket()

        self.t = None
        self.handler = None
        self.songname = None
        self.start_time = None
        self.connected = False
        self.running = False

    def createConnection(self):
        try:
            self.s.settimeout(5)
            self.s.connect(self.addr)
        except socket.error:
            return

        self.t = Transfer(self.s)
        self.t.send(self.client.username.encode())
        response = self.t.recvData()
        if not response == b"success":
            return
        
        self.s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        self.connected = True
        return True

    def downloadThread(self, songname):
        if not self.connected: return
        self.start_time = time.perf_counter()
        self.songname = songname
        songpath = self.client.controller.cache.sharedmusic + songname
        self.t.send(songname.encode())
        try:
            songsize = int(self.t.recvData())
        except:
            return

        self.running = True
        self.handler = SongReceiver(songpath, songname, songsize)
        threading.Thread(target=self.downloadStatusThread, daemon=True).start()

        while self.running:
            data = self.t.recvData()
            if not data:
                break

            if self.handler.write(data):
                self.client.controller.downloadSuccess()
                self.kill()
                break

    def downloadStatusThread(self):
        while self.running:
            if not self.handler: return
            percent = self.handler.getPercent()
            self.client.controller.updateDownloadStatus(self.songname, percent)
            time.sleep(0.5)

    def kill(self):
        self.connected = False
        self.running = False
        if self.handler: self.handler.close()
        try:
            self.s.shutdown(2)
            self.s.close()
        except: pass