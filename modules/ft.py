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

class SongHandler:
    def __init__(self, server, t, username, songname, songsize):
        self.server = server
        self.t = t

        self.username = username
        self.songname = songname
        self.songsize = songsize
        self.received = 0
        self.started = time.perf_counter()
        self.done = False

        self.server.transmitAllExceptMe(f"{self.username} is started uploading!", "blue", self.username)
        os.makedirs("servermusic/uploading/", exist_ok=True)
        self.f = open("servermusic/uploading/"+self.songname+".upload", "ab")
        threading.Thread(target=self.resultThread, daemon=True).start()

    def resultThread(self):
        while not self.done:
            now = time.perf_counter() - self.started
            result = self.received/now
            self.t.sendDataPickle(
                [
                    int(result),
                    self.received
                ]
            )
            time.sleep(0.5)

    def write(self, data):
        if self.done: return
        self.f.write(data)
        self.received += len(data)
        if self.received == self.songsize:
            self.success()

    def abort(self):
        self.done = True
        self.f.close()
        try:
            os.remove("servermusic/uploading/" + self.songname + ".upload")
        except:
            pass
        self.server.transmitAllExceptMe(f"{self.username} has canceled the upload...", "blue", self.username)

    def success(self):
        self.close()
        self.t.send(b"receivedSuccess")
        moveFile("servermusic/uploading/"+self.songname+".upload", "servermusic/"+self.songname)
        self.server.player.addTrack(self.songname)
        self.server.transmitAllExceptMe(f"{self.username} has uploaded the song!!!",
                "blue", self.username)

    def close(self):
        self.done = True
        self.f.close()

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

class ClientFT:
    def __init__(self, client, ip, port):
        self.client = client
        self.ip = ip
        self.port = port
        self.addr = (ip,port)

        self.running = False

        self.s = socket.socket()
        self.stopUploading = False

    def connect(self):
        try:
            self.s.settimeout(5)
            self.s.connect(self.addr)
            self.s.settimeout(None)
            self.s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        except socket.error:
            pass

        self.t = Transfer(self.s)
        self.t.send(self.client.username.encode())
        response = self.t.recvData()
        if response != b"gotall":
            return

        return True
    
    def statusReceiver(self):
        while True:
            data = self.t.recvData()
            if not data or data == b"drop":
                break

            if data == b"receivedSuccess":
                self.client.app.log_frame.upload_win.onReceive()
                break

            speed, received = pickle.loads(data)
            try:
                self.client.app.log_frame.upload_win.updateStatus(speed, 
                    received)
            except:
                pass
        self.suicide()

    def upload(self, path):
        if self.running: return
        self.running = True
        songname = os.path.basename(path)
        songsize = os.path.getsize(path)
        self.t.sendDataPickle(
            {
                "method": "upload",
                "songname": songname,
                "songsize": songsize
            }
        )
        self.t.recvData()
        threading.Thread(target=self.statusReceiver, daemon=True).start()
        with open(path, "rb") as f:
            while not self.stopUploading:
                song = f.read(1024*4)
                if not song:
                    break
                self.t.send(song)
            else:
                self.suicide()

        self.running = False
        return True

    def download(self, songname, songsize):
        if self.running: return
        self.running = True
        self.t.sendDataPickle({
            "method": "download",
            "songname": songname
        })

        f = open(self.client.app.cache.sharedmusic + songname, "wb")
        recvd = 0
        success = False

        while True:
            data = self.t.recvData()
            if not data or data == b"drop":
                break
            f.write(data)
            recvd += len(data)

            if recvd == songsize:
                success = True
                break
        
        f.close()
        self.suicide()
        return success

    def suicide(self):
        self.s.close()