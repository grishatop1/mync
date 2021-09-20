import pickle
import socket
import threading
import time
import os

from transfer import Transfer

class ServerPlayer:
    PATH = "sharedmusic/"
    def __init__(self, server) -> None:
        self.server = server
        self.waiting_song = None
        self.current_playing = None
        self.current_started_time = 0
        self.people_ready = 0

        self.tracks = self.loadTracks()

    def loadTracks(self):
        tracks = os.listdir(self.PATH)
        output = {}
        for track in tracks:
            with open(self.PATH+track, "rb") as f:
                data = f.read() 
            output[track] = hash(data)
        return output

    def addTrack(self, songname):
        with open(self.PATH+songname, "rb") as f:
            data = f.read()
        self.tracks[songname] = hash(data)


class Server:
    os.makedirs("sharedmusic/", exist_ok=True)
    def __init__(self, ip, port) -> None:
        self.ip = ip
        self.port = port
        self.addr = (ip,port)

        self.s = socket.socket()

        self.connections = {}
        self.connthreads = []
        self.snd_connections = []

        self.player = ServerPlayer(self)

    def runServer(self):
        self.s.bind(self.addr)
        self.s.listen()

        print(f"Server started on {self.addr[0]}:{self.addr[1]}")
        self.acceptThread()

    def acceptThread(self):
        while True:
            conn, addr = self.s.accept()
            thread = threading.Thread(target=self.clientHandler, args=(conn,addr),daemon=True).start()
            self.connthreads.append(thread)

    def clientHandler(self, conn, addr):
        print(f"Handling {addr[0]}:{addr[1]}")
        conn.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        t = Transfer(conn)
        username = t.recvData().decode()

        if username in self.connections:
            t.send(b"usernametaken")
            return

        t.sendDataPickle(self.snd_connections)
        response = t.recvData()
        if response != b"gotall": return

        self.connections[username] = [conn, addr, t]
        self.snd_connections.append(username)
        print(f"{username} connected to the server!")
        self.sendAll(pickle.dumps(
            {"method":"connectionplus", "user":username}
        ))

        if self.player.current_playing:
            t.sendDataPickle({"method": "checksong", "songname":self.player.current_playing})

        while True:
            dataraw = t.recvData()
            if not dataraw or dataraw == b"drop":
                break

            data = pickle.loads(dataraw)
            
            if data["method"] == "song":
                self.transmitAllExceptMe(f"{username} is uploading a song!", "blue", username)
                songname = data["songname"]
                song = t.recvData()
                if not song or song == b"drop":
                    break
                with open(self.player.PATH+songname, "wb") as f:
                    f.write(song)
                self.player.addTrack(songname)
                t.sendDataPickle({"method": "songrecvd"})
                self.transmitAllExceptMe(f"{username} has uploaded a song!", "blue", username)

            elif data["method"] == "gettracks":
                t.sendDataPickle({"method": "returnTracks", "data":self.player.tracks})

            elif data["method"] == "req":
                self.player.current_playing = None
                self.player.people_ready = 0
                songname = data["songname"]
                self.player.waiting_song = songname
                self.sendAll(pickle.dumps(
                    {"method":"checksong","songname":songname}
                ))

            elif data["method"] == "reqsongfile":
                songname = data["songname"]
                t.sendDataPickle({"method":"sendingsong", "songname": songname})
                with open(self.player.PATH+songname, "rb") as f:
                    data = f.read()
                t.send(data)

            elif data["method"] == "ready":
                if self.player.current_playing:
                    t.sendDataPickle(
                        {
                            "method":"playtime",
                            "songname": self.player.current_playing,
                            "time": time.perf_counter()-self.player.current_started_time
                        }
                    )
                    continue
                self.player.people_ready += 1
                if self.player.people_ready == len(self.connections):
                    self.player.current_playing = self.player.waiting_song
                    self.player.current_started_time = time.perf_counter()
                    self.sendAll(b"play"+self.player.waiting_song.encode())

            elif data["method"] == "transmit":
                self.transmitAllExceptMe(data["message"], data["color"], username)
                

        del self.connections[username]
        self.snd_connections.remove(username)
        self.sendAllExceptMe(pickle.dumps(
            {"method":"connectionminus", "user":username}
        ), username)
        print(f"{username} has disconnected from the server.")

    def sendAll(self, data):
        for username in self.connections:
            self.connections[username][2].send(data)

    def sendAllExceptMe(self, data, senderUsername):
        for username in self.connections:
            if username == senderUsername:
                continue
            else:
               self.connections[username][2].send(data)

    def transmitAllExceptMe(self, message, color, username):
        self.sendAllExceptMe(pickle.dumps(
            {"method":"transmit", "message": message, "color":color}
        ), username)


if __name__ == "__main__":
    server = Server(socket.gethostbyname(socket.gethostname()), 8888)
    server.runServer()
