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
            self.close()

    def abort(self):
        self.done = True
        self.f.close()
        try:
            os.remove("servermusic/uploading/" + self.songname + ".upload")
        except:
            pass
        self.server.transmitAllExceptMe(f"{self.username} has canceled the upload...", "blue", self.username)

    def close(self):
        self.t.send(b"receivedSuccess")
        self.done = True
        self.f.close()
        moveFile("servermusic/uploading/"+self.songname+".upload", "servermusic/"+self.songname)
        self.server.player.addTrack(self.songname)
        self.t.sendDataPickle(
            {
                "method":"songReceived"
            }
        )
        self.server.transmitAllExceptMe(f"{self.username} has uploaded the song!!!",
                "blue", self.username)

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

        data = t.recvData()
        songname, songsize = pickle.loads(data)
        client.songhandler = SongHandler(self.server, t, username, songname, songsize)

        while True:
            data = t.recvData()
            if not data or data == b"drop":
                client.songhandler.abort()
                break
   
            client.songhandler.write(data)

class ClientFT:
    def __init__(self, client, ip, port):
        self.client = client
        self.ip = ip
        self.port = port
        self.addr = (ip,port)

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
        songname = os.path.basename(path)
        songsize = os.path.getsize(path)
        self.t.sendDataPickle(
            [songname, songsize]
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
        return True

    def suicide(self):
        self.s.close()