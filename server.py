import pickle
import socket
import threading
import time
import os

from tkinter import *
from tkinter import messagebox
from tkinter import filedialog
from tkinter.ttk import *

from modules.transfer import Transfer
from modules.ft import ServerFT

class ServerPlayer:
    PATH = "sharedmusic/"
    UPLOAD_PATH = "sharedmusic/uploading/"
    def __init__(self, server) -> None:
        self.server = server
        self.waiting_song = None
        self.current_playing = None
        self.current_started_time = 0
        self.people_ready = 0

        self.tracks = self.loadTracks()

    def loadTracks(self):
        tracks = [f for f in os.listdir('sharedmusic/') if os.path.isfile("sharedmusic/"+f)]
        return tracks

    def addTrack(self, songname):
        if not songname in self.tracks:
            self.tracks.append(songname)

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
                self.server.player.current_playing = None
                self.server.player.people_ready = 0
                songname = data["songname"]
                self.server.player.waiting_song = songname
                self.server.sendAll(pickle.dumps(
                    {"method":"checksong","songname":songname}
                ))

            elif data["method"] == "reqsongfile":
                songname = data["songname"]
                self.t.sendDataPickle({"method":"sendingsong", "songname": songname})
                with open(self.server.player.PATH+songname, "rb") as f:
                    data = f.read()
                self.t.send(data)

            elif data["method"] == "ready":
                if self.server.player.current_playing:
                    self.t.sendDataPickle(
                        {
                            "method":"playtime",
                            "songname": self.server.player.current_playing,
                            "time": time.perf_counter()-self.server.player.current_started_time
                        }
                    )
                    continue
                self.server.player.people_ready += 1
                if self.server.player.people_ready == len(self.server.connections):
                    self.server.player.current_playing = self.server.player.waiting_song
                    self.server.player.current_started_time = time.perf_counter()
                    self.server.sendAll(b"play"+self.server.player.waiting_song.encode())

            elif data["method"] == "transmit":
                self.t.sendDataPickle(
                    {"method":"echo", "msg": data["message"]}
                )
                self.server.transmitAllExceptMe(
                    f"[{self.username}]: {data['message']}", 
                    data["color"],
                    self.username)

            elif data["method"] == "im-muted":
                self.server.renameSndUser(self.username, self.username+" (muted)")
                self.server.sendAll(
                    pickle.dumps(
                        {"method":"in-mute", "user": self.username}
                    )
                )

            elif data["method"] == "im-unmuted":
                self.server.renameSndUser(self.username+" (muted)", self.username)
                self.server.sendAll(
                    pickle.dumps(
                        {"method":"in-outmute", "user": self.username}
                    )
                )
                

        del self.server.connections[self.username]
        self.server.removeSndUser(self.username)
        self.server.sendAllExceptMe(pickle.dumps(
            {"method":"connectionminus", "user":self.username}
        ), self.username)
        print(f"{self.username} has disconnected from the server.")

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

    def runServer(self):
        self.s.bind(self.addr)
        self.s.listen()

        print(f"Server started on {self.addr[0]}:{self.addr[1]}")
        self.ft = ServerFT(self, self.ip, self.port+1)
        self.player = ServerPlayer(self)
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

        client = ClientHandler(self, username, conn, t)
        self.connections[username] = client
        self.snd_connections.append(username)
        print(f"{username} connected to the server!")

        if self.player.current_playing:
            t.sendDataPickle({"method": "checksong", "songname":self.player.current_playing})

        self.sendAllExceptMe(pickle.dumps(
            {"method": "connectionplus", "user": username}
        ), username)

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

    def renameSndUser(self, old, new):
        try:
            self.snd_connections.remove(old)
            self.snd_connections.append(new)
        except:pass

    def removeSndUser(self, username):
        try:
            self.snd_connections.remove(username)
        except:
            self.snd_connections.remove(username+" (muted)")


if __name__ == "__main__":
    main=Tk()
    main.title("Mync Server")
    main.geometry("255x100")
    main.resizable(False,False)

    runInstantly = True
    if runInstantly:
        server = Server("192.168.0.33", 8888)
        server.runServer()
        quit()

    def help_(*args):
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
    def entrytog(*args):
        if not custom_port_cbox_var.get():
            custom_port_entry["state"]="readonly"
            custom_port_entry["foreground"]="grey"
            custom_port_entry.delete(0,"end")
            custom_port_var.set("8888")
        else:
            custom_port_entry["state"]=""
            custom_port_entry["foreground"]="black"
            custom_port_entry.delete(0,"end")
            custom_port_entry.insert(0, "")
            custom_port_entry.focus()

    def thread():
        threading.Thread(target=start,daemon=True).start()

    def start(*args):
        try:
            startB["text"]="Close server"
            startB["command"]=exitcond
            #if custom port
            if custom_port_var.get() and custom_port_cbox_var.get():
                #start server with custom port
                server = Server(socket.gethostbyname(socket.gethostname()),
                                int(custom_port_var.get()))
                server.runServer()
                
            else:
                #start server with port 8888
                server = Server(socket.gethostbyname(socket.gethostname()),
                                8888)
                server.runServer()
        except Exception as error:
            messagebox.showerror(
            "Error!","The following error has occured:\n\n\"{}\"".format(error))

    def exitcond(*args):
        if (res2 := messagebox.askyesno("Are you sure?","Close server?")):
            main.destroy()
        

    #checkbox variable
    custom_port_cbox_var=IntVar()
    custom_port_cbox_var.set(0)

    #checkbox
    custom_port_cbox=Checkbutton(main, text="Custom port (advanced)",
                       variable=custom_port_cbox_var,command=entrytog)
    custom_port_cbox.grid(column=0,row=0,sticky="we",padx=50,pady=3)

    #port entry variable
    custom_port_var=StringVar(value="8888")

    #port entry
    custom_port_entry=Entry(main, textvariable=custom_port_var,
                            state="readonly",width=20,foreground="grey")
    custom_port_entry.grid(column=0,row=1,sticky="we",padx=50)

    #start button
    startB=Button(main, text="Start Server",command=thread)
    startB.grid(column=0,row=2,columnspan=3,sticky="we",padx=50,pady=10)

    #bind to help window
    main.bind("<F1>",help_)
    
    #bind to start server
    main.bind("<F3>",thread)

    #menu config
    menu = Menu(main)
    menu.add_command(label="How to Use", command=help_, underline=0)
    main.config(menu=menu)

    main.mainloop()
