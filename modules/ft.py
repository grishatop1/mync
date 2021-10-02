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
        try:
            username = t.recvData().decode()
        except: return
        if not username in self.server.connections:
            t.send(b"badusername")
            return
        client = self.server.connections[username]
        t.send(b"success")

        response = t.recvData()
        data = pickle.loads(response)
        if data["method"] == "upload":
            songname, songsize = data["songname"], data["songsize"]
            songpath = "servermusic/"+songname
            client.started = time.perf_counter()
            client.songhandler = SongReceiver(songpath, songname, songsize)
            t.send(b"ready")
            threading.Thread(
                target=self.getterStatus,
                args=(client, t, client.songhandler),
                daemon=True
            ).start()
            while True:
                #time.sleep(0.05) #bad net simulator
                data = t.recvData()
                if not data or data == b"drop":
                    break
                if client.songhandler.write(data):
                    t.send(b"done")
                    self.server.player.addTrack(songname)
                    self.server.transmitAllExceptMe(f"{username} has uploaded the song!!!",
                            "blue", username)
                    break

            client.songhandler.close()

        elif data["method"] == "download":
            self.server.transmitAllExceptMe(
                f"{username} is downloading...",
                "blue",
                username    
            )
            songname = data["songname"]
            songpath = "servermusic/" + songname
            t.send(str(os.path.getsize(songpath)).encode())
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

    def getterStatus(self, client, t, songhandler):
        while not songhandler.closed:
            now = time.perf_counter() - client.started
            result = songhandler.recvd/now
            snd = f"{result}:{songhandler.recvd}"
            t.send(snd.encode())
            time.sleep(0.5)

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
            self.close()
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
            self.s.settimeout(None)
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
        if self.running: return
        if not self.connected: return
        self.start_time = time.perf_counter()
        self.songname = songname
        songpath = self.client.controller.cache.sharedmusic + songname
        self.t.sendDataPickle(
            {"method": "download", "songname": songname}
        )
        try:
            songsize = int(self.t.recvData())
        except:
            self.client.controller.downloadFail()
            self.kill()
            return

        self.running = True
        self.handler = SongReceiver(songpath, songname, songsize)
        threading.Thread(target=self.downloadStatusThread, daemon=True).start()

        while self.running:
            data = self.t.recvData()
            if not data and self.running:
                self.client.controller.downloadFail()
                break

            if self.handler.write(data):
                self.client.controller.downloadSuccess()
                self.client.sendReady()
                break

        self.kill()

    def downloadStatusThread(self):
        while self.running:
            if not self.handler: return
            percent = self.handler.getPercent()
            self.client.controller.updateDownloadStatus(self.songname, percent)
            time.sleep(0.5)

    def uploadThread(self, songpath):
        if self.running: return
        if not self.connected: return
        self.start_time = time.perf_counter()
        self.songname = os.path.basename(songpath)
        songsize = os.path.getsize(songpath)

        self.t.sendDataPickle(
            {"method": "upload", "songname": self.songname, "songsize": songsize}
        )

        response = self.t.recvData()
        if not response == b"ready":
            self.client.controller.uploadFail()
            self.kill()
            return

        self.running = True
        threading.Thread(target=self.uploadStatusThread, daemon=True).start()

        with open(songpath, "rb") as f:
            while self.running:
                data = f.read(1024*4)
                if not data:
                    break
                self.t.send(data)

    def uploadStatusThread(self):
        while self.running:
            data = self.t.recvData()
            if not data:
                self.kill()
                break
            if data == b"done":
                self.kill()
                self.client.controller.uploadSuccess()
                break

            speed, recvd = data.decode().split(":")
            ispeed, irecvd = float(speed), float(recvd)
            self.client.controller.updateUploadStatus(
                ispeed, irecvd
            )

    def kill(self):
        self.connected = False
        self.running = False
        if self.handler: self.handler.close()
        try:
            self.s.shutdown(2)
        except: pass
        self.s.close()