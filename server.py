import pickle
import socket
import threading
import time
import queue
import os

from tkinter import *
from tkinter import messagebox
from tkinter import filedialog
from tkinter.ttk import *

from modules.transfer import Transfer
from modules.ft import ServerFT

from pytube import YouTube
from pytube import Search

from requests import get, post
from bs4 import BeautifulSoup
from moviepy.editor import AudioFileClip
from mutagen.mp3 import MP3

class CurrentPlayingTimer:
    def __init__(self, server, path, callback) -> None:
        self.server = server
        self.path = path
        self.callback = callback
        self.stopped = False
    
    def start(self):
        self.stopped = False
        self.audio = MP3(self.path)
        threading.Thread(target=self.run, args=()).start()

    def run(self):
        time.sleep(self.audio.info.length)
        if not self.stopped:
            self.callback()

    def stop(self):
        self.stopped = True


class YTHandler:
    def __init__(self, client, link, obj=False) -> None:
        self.client = client
        self.link = link
        self.obj = obj
        threading.Thread(target=self.downloadMP3, daemon=True).start()

    def downloadMP3(self):
        if not self.obj:
            yt = YouTube(self.link).streams.filter(only_audio=True).first()
        else:
            yt = self.link.streams.filter(only_audio=True).first()
        yt.download("servermusic/")
        songname, songext = os.path.splitext(yt.default_filename)
        songnamefull = yt.default_filename

        video = AudioFileClip(
            os.path.join("servermusic", songnamefull)
        )
        video.write_audiofile(
            os.path.join("servermusic", songname+".mp3"), logger=None
        )
        self.client.server.player.addTrack(
            songname + ".mp3"
        )
        os.remove("servermusic/"+songnamefull)

        self.client.transmitMe(
            "server_downloaded",
            "green"
        )

class YTSearcher:
    def __init__(self, client, keyword) -> None:
        self.client = client
        self.keyword = keyword
        self.handler = None
        threading.Thread(target=self.searchAndRequest, daemon=True).start()

    def searchAndRequest(self):
        s = Search(self.keyword)
        result = s.results[0]
        self.client.transmitMe(
            "server_found_track", 
            "black",
            result.title
            )
        self.handler = YTHandler(self.client, result, obj=True)

class ServerPlayer:
    PATH = "servermusic/"
    UPLOAD_PATH = "servermusic/uploading/"
    def __init__(self, server) -> None:
        self.server = server
        self.waiting_song = None
        self.current_playing = None
        self.current_started_time = 0
        self.current_started_timetime = None
        self.people_ready = 0
        self.tracks = self.loadTracks()
        self.current_timer = None

        self.cmd_queue = queue.Queue()

        threading.Thread(target=self.playAwaiter, daemon=True).start()

    def loadTracks(self):
        tracks = [f for f in os.listdir('servermusic/') if os.path.isfile("servermusic/"+f)]
        return tracks

    def addTrack(self, songname):
        if not songname in self.tracks:
            self.tracks.append(songname)

    def newSongRequest(self, songname):
        self.cmd_queue.put(
            {"method": "req", "songname": songname}
        )

    def newUserIsReady(self):
        self.cmd_queue.put(
            {"method": "ready"}
        )

    def stopPlaying(self):
        if self.current_timer:
            self.current_timer.stop()
        self.current_playing = None
        self.people_ready = 0
        self.server.sendAll(pickle.dumps({"method": "stop"}))

    def playAwaiter(self):
        while True:
            cmd = self.cmd_queue.get()
            if cmd["method"] == "req":
                self.current_playing = None
                self.people_ready = 0
                self.waiting_song = cmd["songname"]
                self.server.sendAll(pickle.dumps({
                    "method": "checksong",
                    "songname": cmd["songname"]
                }))

            elif cmd["method"] == "ready":
                self.people_ready += 1
                if self.people_ready == len(self.server.connections):
                    self.current_playing = self.waiting_song
                    self.waiting_song = None
                    self.current_started_time = time.perf_counter()
                    self.server.current_started_timetime = time.time()
                    self.server.sendAll(pickle.dumps(
                        {
                            "method": "play",
                            "songname": self.current_playing,
                            "play_at": self.current_started_timetime,
                            "starttime": 0
                        }
                    ))
                    if self.current_timer:
                        self.current_timer.stop()
                    self.current_timer = CurrentPlayingTimer(
                        self.server,
                        self.PATH+self.current_playing,
                        self.stopPlaying
                    )
                    self.current_timer.start()

class ClientHandler:
    def __init__(self, server, username, sock, transport):
        self.server = server
        self.username = username
        self.s = sock
        self.t = transport

        self.songhandler = False

    def mainThread(self):
        while True:
            dataraw = self.t.recvData()
            if not dataraw or dataraw == b"drop":
                break

            data = pickle.loads(dataraw)

            if data["method"] == "gettracks":
                self.t.sendDataPickle({"method": "returnTracks", "data":self.server.player.tracks})

            elif data["method"] == "req":
                self.server.player.newSongRequest(data["songname"])

            elif data["method"] == "ready":
                if self.server.player.waiting_song:
                    self.server.player.newUserIsReady()
                else:
                    self.t.sendDataPickle(
                        {
                            "method": "play",
                            "songname": self.server.player.current_playing,
                            "play_at": self.server.player.current_started_timetime,
                            "starttime": time.perf_counter() - self.server.player.current_started_time
                        }
                    )

            elif data["method"] == "req-yt":
                self.transmitMe(
                    "server_downloading",
                    "black"
                )
                YTHandler(self, data["link"])

            elif data["method"] == "reqsongfile":
                songname = data["songname"]
                self.t.sendDataPickle({"method":"sendingsong", "songname": songname})
                with open(self.server.player.PATH+songname, "rb") as f:
                    data = f.read()
                self.t.send(data)

            elif data["method"] == "transmit":
                self.t.sendDataPickle(
                    {"method":"echo", "msg": data["message"]}
                )
                self.server.sendAllExceptMe(
                    pickle.dumps({
                        "method": "client-msg",
                        "message": data["message"],
                        "sender": self.username
                    }), self.username
                )

            elif data["method"] == "suffix":
                sfx = data["suffix"]
                self.server.changeConnectionSuffix(
                    self.username, sfx
                )

            elif data["method"] == "command":
                cmd = data["cmd"]
                content = data["content"]
                if cmd == "search":
                    self.transmitMe(
                    "server_search",
                    "black"
                    )
                    YTSearcher(self, content)
                

        del self.server.connections[self.username]
        self.server.removeConnection(self.username)
        print(f"{self.username} has disconnected from the server.")

    def transmitMe(self, msg_id, color, *args):
        self.t.sendDataPickle({
            "method": "server-msg", 
            "msg_id": msg_id,
            "args": args,
            "color": color
            })

class Server:
    os.makedirs("servermusic/", exist_ok=True)
    def __init__(self, ip, port) -> None:
        self.ip = ip
        self.port = port
        self.addr = (ip,port)

        self.s = socket.socket()

        self.connections = {}
        self.connthreads = []
        self.snd_connections = {}

    def runServer(self):
        self.s.bind(self.addr)
        self.s.listen()

        print(f"Server started on {self.addr[0]}:{self.addr[1]}")
        self.ft = ServerFT(self, self.ip, self.port+1)
        self.player = ServerPlayer(self)

        threading.Thread(target=self.publicIp, daemon=True).start()

        self.acceptThread()

    def publicIp(self):
        try:
            ip = get('https://api.ipify.org').text
            print(f"Your public IP: {ip}:{self.port}")
            self.portCheck(ip)
        except:
            pass

    def portCheck(self, ip):
        try:
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            data = {"remoteAddress":ip, "portNumber":self.port}
            url = "https://ports.yougetsignal.com/check-port.php"
            response = post(url, data=data, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            print(soup.get_text()[1:])
        except Exception as e:
            print(str(e))

    def acceptThread(self):
        while True:
            conn, addr = self.s.accept()
            thread = threading.Thread(target=self.clientHandler, args=(conn,addr),daemon=True).start()
            self.connthreads.append(thread)

    def clientHandler(self, conn, addr):
        print(f"Handling {addr[0]}:{addr[1]}")
        #conn.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        t = Transfer(conn)
        try:
            username = t.recvData().decode()
        except: return

        if username in self.connections:
            t.send(b"usernametaken")
            return

        data = {
            "connections": self.snd_connections,
            "ft-port": self.port+1
        }
        t.sendDataPickle(data)
        response = t.recvData()
        if response != b"gotall": return

        client = ClientHandler(self, username, conn, t)
        self.connections[username] = client
        print(f"{username} connected to the server!")

        if self.player.current_playing:
            songpath = "servermusic/"+self.player.current_playing
            songsize = os.path.getsize(songpath)
            t.sendDataPickle(
                {
                    "method": "checksong", 
                    "songname":self.player.current_playing
                }
            )

        self.addUserToConnections(username)
        client.mainThread()

    def sendAll(self, data):
        for username in self.connections:
            self.connections[username].t.send(data)

    def sendAllExceptMe(self, data, senderUsername):
        for username in self.connections:
            if username == senderUsername:
                continue
            else:
               self.connections[username].t.send(data)

    def transmitAllExceptMe(self, message, color, username):
        self.sendAllExceptMe(pickle.dumps(
            {"method":"transmit", "message": message, "color":color}
        ), username)

    def addUserToConnections(self, username):
        self.snd_connections[username] = ""
        self.sendAllExceptMe(pickle.dumps(
            {"method": "connectionplus", "user": username}
        ), username)

    def changeConnectionSuffix(self, username, suffix):
        self.snd_connections[username] = suffix
        self.sendAll(pickle.dumps(
            {"method": "set-suffix", "username": username, "suffix": suffix}
        ))

    def removeConnection(self, username):
        del self.snd_connections[username]
        self.sendAllExceptMe(pickle.dumps(
            {"method":"connectionminus", "user":username}
        ), username)

class LauncherGUI(Tk):
    def __init__(self, debug=False, *args, **kwargs) -> None:
        Tk.__init__(self, *args, **kwargs)

        self.debug = debug
        if self.debug:
            self.startNoGUI()
            return

        self.title("Mync Server")
        self.resizable(False,False)

        self.custom_port_cbox_var=IntVar()
        self.custom_port_cbox_var.set(0)

        self.custom_port_cbox=Checkbutton(self, text="Custom port (advanced)",
                        variable=self.custom_port_cbox_var,command=self.entrytog)
        self.custom_port_cbox.grid(column=0,row=0,sticky="we",padx=50,pady=3)

        self.custom_port_var=StringVar(value="8888")

        self.custom_port_entry=Entry(self, textvariable=self.custom_port_var,
                                state="readonly",width=20,foreground="grey")
        self.custom_port_entry.grid(column=0,row=1,sticky="we",padx=50)

        self.startB=Button(self, text="Start server",command=self.thread)
        self.startB.grid(column=0,row=2,columnspan=3,sticky="we",padx=50,pady=10)

        self.bind("<F1>",self.help_)
        self.bind("<F3>",self.thread)

        self.menu = Menu(self)
        self.menu.add_command(label="How to Use", command=self.help_, underline=0)
        self.config(menu=self.menu)

    def help_(self, *args):
        messagebox.showinfo(title="How to use",message=
            """0) Please read before use:

1) The default port is 8888, but you can also set a custom port. First
check the 'Custom Port' checbox, and then type in the preferred
port. The checkbox must remain checked in order to use the custom
port.

2) Pressing the 'Start Server' button will start the server on the
custom port or port 8888. Pressing it again will stop the server and
close the launcher. You can also press F3 to launch the server.""")

    #checkbox toggler for entry box
    def entrytog(self, *args):
        if not self.custom_port_cbox_var.get():
            self.custom_port_entry["state"]="readonly"
            self.custom_port_entry["foreground"]="grey"
            self.custom_port_entry.delete(0,"end")
            self.custom_port_var.set("8888")
        else:
            self.custom_port_entry["state"]=""
            self.custom_port_entry["foreground"]="black"
            self.custom_port_entry.delete(0,"end")
            self.custom_port_entry.insert(0, "")
            self.custom_port_entry.focus()

    def thread(self):
        self.focus()
        threading.Thread(target=self.start,daemon=True).start()

    def start(self, *args):
        try:
            self.startB["text"]="Close server"
            self.startB["command"]=self.exitcond
            #if custom port
            if self.custom_port_var.get() and self.custom_port_cbox_var.get():
                #start server with custom port
                server = Server(socket.gethostbyname(socket.gethostname()),
                                int(self.custom_port_var.get()))
                server.runServer()
                
            else:
                #start server with port 8888
                server = Server(socket.gethostbyname(socket.gethostname()),
                                8888)
                server.runServer()
        except Exception as error:
            messagebox.showerror(
            "Error!","The following error has occured:\n\n\"{}\"".format(error))

    def startNoGUI(self):
        server = Server(socket.gethostbyname(socket.gethostname()),
                                8888)
        server.runServer()

    def exitcond(self, *args):
        self.destroy()


if __name__ == "__main__":
    app = LauncherGUI(debug=True)
    app.mainloop()
