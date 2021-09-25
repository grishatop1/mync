from modules.ft import ClientFT
import os
import time
import socket
import pickle
import threading
import pygame.mixer

from tkinter import *
from tkinter import messagebox
from tkinter.ttk import *
from tkinter.messagebox import *
from tkinter import filedialog

from modules.transfer import Transfer
from modules.pypresence import Presence

from shutil import copyfile

class CacheManager:
    def __init__(self):
        self.appdata = os.getenv('APPDATA').replace("\\", "/")
        self.cache_path = self.appdata+"/.mync/"
        self.cache_file = self.cache_path+"cache.temp"
        self._checkInitial()

    def _checkInitial(self):
        #checks if program was started for the first time
        if not os.path.exists(self.cache_file):
            self._check()
            data = {
                "volume": 80,
                "ip": "",
                "username": ""
            }
            with open(self.cache_file, "wb") as f:
                pickle.dump(data, f)
    
    def _check(self):
        os.makedirs(self.cache_path, exist_ok=True)
        open(self.cache_file, "ab").close()

    def _load(self):
        self._check()
        with open(self.cache_file, "rb") as f:
            self.data = pickle.load(f)

    def read(self, key):
        self._load()
        try:
            return self.data[key]
        except:
            return None

    def write(self, key, value):
        self._load()
        self.data[key] = value
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.data, f)

class Client:
    def __init__(self, app, ip, port, username):
        self.app = app
        self.ip = ip
        self.port = port
        self.addr = (ip,port)
        self.username = username
        self.s = socket.socket()

        self.force_disconnect = False
        self.alive = False
    
    def connect(self):
        try:
            self.s.settimeout(5)
            self.s.connect(self.addr)
            self.alive = True
        except socket.error:
            self.app.connect_frame.setNormalState()
            showwarning("Connection", "Connection failed.")
            return
        except Exception as e:
            print(e)
            showerror("Client", "Maybe there is an error in the inputs. "+
                      "Check them and try again.")
            return

        self.s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        self.t = Transfer(self.s)
        self.t.send(self.username.encode())
        connections = self.t.recvData()
        if connections == b"usernametaken":
            self.app.connect_frame.setNormalState()
            showwarning("Connection", "Username is already taken.")
            return
        try:
            users = pickle.loads(connections)
        except:
            self.app.connect_frame.setNormalState()
            showwarning("Connection", "Couldn't connect to the server.")
            return

        self.t.send(b"gotall")
        self.s.settimeout(None)
        threading.Thread(target=self.mainThread, daemon=True).start()

        self.app.connections_frame.addUsers(users)
        self.app.connections_frame.addUser(self.username)
        self.app.connect_frame.setConnectedState()
        showinfo("Connection", "Connected to the server!")

        self.app.cache.write("ip", f"{self.addr[0]}:{self.addr[1]}")
        self.app.cache.write("username", self.username)

    def disconnect(self):
        self.force_disconnect = True
        self.alive = False
        self.t.send(b"drop")
        self.s.close()

    def mainThread(self):
        while self.alive:
            data = self.t.recvData()
            if not data or data == b"drop":
                break
            
            if data[:4] == b"play":
                songname = data[4:].decode()
                try:
                    self.app.player_frame.playTrack(songname)
                    self.app.log(f"Playing {songname}", "green")
                except:
                    showerror("Player", "Error playing track!")
                continue

            data = pickle.loads(data)

            if data["method"] == "songReceived":
                self.app.log_frame.upload_win.onReceive()
            
            elif data["method"] == "returnTracks":
                if self.app.log_frame.req_win:
                    self.app.log_frame.req_win.loadTracks(data["data"])

            elif data["method"] == "checksong":
                songname = data["songname"]
                tracks = os.listdir("./sharedmusic/")
                if not songname in tracks:
                    self.t.sendDataPickle(
                        {"method": "reqsongfile", "songname": songname}
                    )
                    self.app.log("Missing song :( Requesting it...", "red")
                else:
                    self.t.sendDataPickle(
                        {"method": "ready", "songname": songname}
                    )
                    self.app.log(
                        "Ready for the next song! Waiting for others...")

            elif data["method"] == "sendingsong":
                songname = data["songname"]
                self.app.mainstatus_label["text"] = f"Downloading {songname}"
                self.app.mainstatus_label["foreground"] = "green"
                self.app.log(f"Downloading {songname}")
                data = self.t.recvData()
                if not data or data == b"drop":
                    break
                with open("./sharedmusic/"+songname, "wb") as f:
                    f.write(data)
                self.t.sendDataPickle(
                        {"method": "ready", "songname": songname}
                    )
                self.app.mainstatus_label["text"] = f"NETWORK IDLE"
                self.app.mainstatus_label["foreground"] = "black"
                self.app.log(songname + " has been downloaded!", "green")
                self.app.log("Ready for the song! Waiting for others...")

            elif data["method"] == "connectionplus":
                user = data["user"]
                self.app.connections_frame.addUser(user)

            elif data["method"] == "connectionminus":
                user = data["user"]
                self.app.connections_frame.removeUser(user)

            elif data["method"] == "playtime":
                songname = data["songname"]
                start_time = data["time"]
                try:
                    self.app.player_frame.playTrack(songname, start_time)
                    self.app.log(f"Playing {songname}", "green")
                except:
                    showerror("Player", "Error playing track!")

            elif data["method"] == "transmit":
                self.app.log(data["message"], data["color"])

            elif data["method"] == "echo":
                msg = data["msg"]
                self.app.log_frame.insertTextLine(
                    f"[You]: {msg}",
                    "blue"
                )

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
            self.app.resetAll()
            showerror("Connection", "Connection has been lost.")

    def uploadSong(self, path):
        self.ft = ClientFT(self, self.ip, self.port+1)
        if self.ft.connect():
            self.ft.upload(path)

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

class ConnectFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.client = None

        self.username_label = Label(self, text="Username:")
        self.username_entry = Entry(self)
        self.ip_label = Label(self, text="Server IP:")
        self.ip_entry = Entry(self)
        self.connect_btn = Button(self, text="Connect",
                                  command=self.startConnectThread)

        self.username_label.grid(row=1, column=0, padx=3, pady=3)
        self.username_entry.grid(row=1, column=1, padx=3, pady=3)
        self.ip_label.grid(row=2, column=0, padx=3, pady=3)
        self.ip_entry.grid(row=2, column=1, padx=3, pady=3)
        self.connect_btn.grid(row=3, column=0, columnspan=2, padx=3, pady=3)

        #load cache
        self.ip_entry.insert(0,self.parent.cache.read("ip"))
        self.username_entry.insert(0, self.parent.cache.read("username"))

    def startConnectThread(self):
        if not self.username_entry.get():
            return
        try:
            ip, port = self.ip_entry.get().split(":")
            port = int(port)
        except:
            return

        self.setConnectingState()
        self.client = Client(self.parent, ip, port, self.username_entry.get())
        threading.Thread(target=self.client.connect, daemon=True).start()

    def startDisconnect(self):
        self.client.disconnect()
        self.parent.resetAll()
        showinfo("Connection", "Disconnected!")
        self.client = None

    def setConnectingState(self):
        self.username_entry["state"] = "disabled"
        self.ip_entry["state"] = "disabled"
        self.connect_btn.config(
            text="Connecting...",
            state="disabled"
        )
        root.focus()

    def setNormalState(self):
        self.username_entry["state"] = "normal"
        self.ip_entry["state"] = "normal"
        self.connect_btn.config(
            text="Connect",
            state="normal",
            command=self.startConnectThread
        )

    def setConnectedState(self):
        self.username_entry["state"] = "disabled"
        self.ip_entry["state"] = "disabled"
        self.connect_btn.config(
            text="Disconnect",
            state="normal",
            command=self.startDisconnect
        )

class LogFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.log_text = Text(self, width=40, height=10, state="disabled")
        self.upload_win = None

        colors = ["green", "red", "blue", "black", "orange", "pink"]
        for color in colors:
            self.log_text.tag_configure(color, foreground=color)

        self.upload_btn = Button(self, text="Upload",
                                 command=self.startUploadThread)
        self.req_btn = Button(self, text="Request a song",
                              command=self.startRequestWindow)

        self.log_text.grid(row=1, column=0, columnspan=2, padx=3, pady=3)
        self.upload_btn.grid(row=0, column=0, columnspan=1, pady=3)
        self.req_btn.grid(row=0, column=1, columnspan=1, pady=3)

        self.chat_subframe = ChatSubFrame(self)
        self.chat_subframe.grid(row=2, column=0, columnspan=2, sticky="we")


    def startUploadThread(self):
        if not self.parent.connect_frame.client:
            return
        if not self.parent.connect_frame.client.alive:
            return

        root.focus()
        file = filedialog.askopenfilename(title="Open music file",
                                          filetypes=(("Music Files","*.mp3"),))
        if not file: return

        copyfile(file, "./sharedmusic/"+os.path.basename(file))
        self.parent.setStatusLabel(f"Uploading {os.path.basename(file)}")
        self.parent.log(f"Uploading {os.path.basename(file)}")        
        self.upload_btn.config(state="disabled", text="Uploading...")
        
        self.upload_win = UploadTopLevel(self.parent, file)
        self.upload_win.mainloop()

    def startRequestWindow(self):
        if not self.parent.connect_frame.client:
            return
        if not self.parent.connect_frame.client.alive:
            return

        root.focus()
        self.req_win = RequestTopLevel(self.parent)
        self.req_btn.mainloop()

    def insertTextLine(self, data, color="black"):
        self.log_text["state"] = "normal"
        self.log_text.insert("end", data + "\n", color)
        self.log_text["state"] = "disabled"
        self.log_text.see("end")

    def clearLogs(self):
        self.log_text["state"] = "normal"
        self.log_text.delete("1.0", "end")
        self.log_text["state"] = "disabled"
        
class ChatSubFrame(Frame):
    def __init__(self, parent, *args, **kwargs) -> None:
        Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        
        self.input = PlaceholderEntry(
            self,
            "Enter message",
            style="TEntry",
            placeholder_style="Placeholder.TEntry",
            width=45,
        )
        self.input.bind("<Return>", self.sendMsg)
        self.send_btn = Button(self, text="Send",
                                  command=self.sendMsg, width=5)

        self.input.grid(row=0, column=0, padx=3, pady=3, ipady=1, sticky="we")
        self.send_btn.grid(row=0, column=1, padx=3, pady=3, sticky="e")

    def sendMsg(self, *args):
        self.input.focus()
        msg = self.input.get()
        if not msg: return
        if msg == "Enter message": return
        self.input.delete(0, "end")
        if self.parent.parent.connect_frame.client:
            self.parent.parent.connect_frame.client.transmitMsg(
                msg, 
                "blue"
            )
        else:
           self.parent.insertTextLine(
               f"[Offline]: {msg}",
               "black"
           )

class ConnectionsFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.connections_listbox = Listbox(self, width=30)
        self.connections_listbox.pack(padx=3, pady=3)

    def addUser(self, username):
        self.connections_listbox.insert("end", username)

    def addUsers(self, connections):
        for username in connections:
            self.addUser(username)

    def renameUser(self, username, new):
        try:
            idx = self.removeUser(username)
            self.connections_listbox.insert(idx, new)
        except: pass

    def removeUser(self, username):
        try:
            idx = self.connections_listbox.get(0, "end").index(username)
        except:
            idx = self.connections_listbox.get(0, "end").index(username+" (muted)")
        self.connections_listbox.delete(idx)
        return idx

    def clear(self):
        self.connections_listbox.delete(0, "end")


class PlayerFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.player = None
        self.start_time = 0
        self.last_volume = int(self.parent.cache.read("volume"))

        self.status_label = Label(self, text="Waiting for the track...")
        self.volume_label = Label(self, text="Volume:")
        self.volume_var = IntVar()
        self.volume_scale = Scale(self, from_=0, to=100, 
                                    orient="horizontal",
                                    length=300,
                                    variable=self.volume_var)
        self.volume_scale.bind("<B1-Motion>", self.setvolume)
        self.volume_var.set(
            self.parent.cache.read("volume")
        )
        self.setvolume()

        self.status_label.grid(row=0, column=0, columnspan=2, padx=3, pady=3)
        self.volume_label.grid(row=1, column=0, padx=3, pady=3)
        self.volume_scale.grid(row=1, column=1, padx=3, pady=3)

    def playTrack(self, songname, start_time=0):
        pygame.mixer.music.load("sharedmusic\\"+songname)
        pygame.mixer.music.play(start=start_time, loops=0)
        root.deiconify()
        root.title(f"Mync Client - Playing {songname[:100]}")
        self.status_label.configure(
            text=f"Playing {songname[:80]}",
            foreground="green"
        )
        self.parent.ds_presence.update(
            f"{os.path.splitext(songname[:110])[0]}",
            time.time()
            )

    def stopTrack(self):
        pygame.mixer.music.stop()
        root.title("Mync Client")
        self.status_label.configure(
            text=f"Waiting for the track...",
            foreground="black"
        )

    def setvolume(self, event=None):
        volume = self.volume_var.get()
        pygame.mixer.music.set_volume(volume/100)
        self.parent.cache.write("volume", volume)
        if self.parent.connect_frame.client:
            if volume == 0 and self.last_volume > 0:
                self.parent.connect_frame.client.transmitMuted(True)
            elif self.last_volume == 0 and volume > 0:
                self.parent.connect_frame.client.transmitMuted(False)

        self.last_volume = volume

class PlaceholderEntry(Entry):
    def __init__(self, container,placeholder,placeholder_style,*args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.placeholder = placeholder

        self.field_style = kwargs.pop("style", "TEntry")
        self.placeholder_style=kwargs.pop("placeholder_style",self.field_style)
        self["style"] = self.placeholder_style

        self.insert("0", self.placeholder)
        self["foreground"] = "gray"
        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._add_placeholder)

    def _clear_placeholder(self, e):
        if self["style"] == self.placeholder_style:
            self.delete("0", "end")
            self["style"] = self.field_style
            self["foreground"] = "black"

    def _add_placeholder(self, e):
        if not self.get():
            self.insert("0", self.placeholder)
            self["style"] = self.placeholder_style
            self["foreground"] = "gray"

class RequestTopLevel(Toplevel):
    def __init__(self, parent, *args, **kwargs) -> None:
        Toplevel.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.title("Choose a song...")
        self.resizable(0,0)
        self.geometry("400x250")
        self.grab_set() #get the all controls from root muahaha
        
        self.status_label = Label(self,
                                  text="Requesting songlist from server...")
        self.tracks_list = Listbox(self, width=100)
        self.choose_btn = Button(self, text="Play!", command=self.play)

        self.status_label.pack(padx=5, pady=5)
        self.tracks_list.pack(padx=5, pady=5)
        self.choose_btn.pack(padx=5, pady=10)

        self.reqTracks()
    
    def reqTracks(self):
        threading.Thread(
            target=self.parent.connect_frame.client.getTracks,
            daemon=True
        ).start()

    def loadTracks(self, tracks):
        self.tracks = tracks
        for track in tracks:
            self.tracks_list.insert("end", track)
        self.status_label["text"] = "Pick a song... (scrollable)"

    def play(self):
        try:
            songname = self.tracks_list.get(self.tracks_list.curselection())
        except:
            return
        self.parent.connect_frame.client.reqSong(songname)
        self.destroy()

class UploadTopLevel(Toplevel):
    def __init__(self, parent, file, *args, **kwargs) -> None:
        Toplevel.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.file = file
        self.filename = os.path.basename(file)

        self.title("Upload Window")
        self.resizable(0,0)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.canv_w = 300
        self.canv_h = 80
        self.canv_count = self.canv_h//15
        self.points = []

        self.title_label = Label(self, text=f"Uploading {self.filename[:25]}...")
        self.graph_canvas = Canvas(self, width=self.canv_w, height=self.canv_h, background="white")
        self.speed_label = Label(self, text="Loading...")
        self.percent_label = Label(self, text="Loading...")
        self.cancel_btn = Button(self, text="Cancel", command=self.cancel)

        self.title_label.grid(row=0, column=0, columnspan=2, pady=(10,0))
        self.graph_canvas.grid(row=1, column=0, columnspan=2, padx=15, pady=8)
        self.speed_label.grid(row=2, column=0, padx=3, pady=3)
        self.percent_label.grid(row=2, column=1, padx=3, pady=3)
        self.cancel_btn.grid(row=3, column=0, columnspan=2, padx=3, pady=3)

        self.drawGraph()
        self.start()

    def updateStatus(self, bps, received):
        songsize = round(os.path.getsize(self.file)/1024/1024, 1)
        self.speed_label["text"] = f"{round(bps/1024, 1)}kbps"
        self.percent_label["text"] = f"Sent: {round(received/1024/1024, 1)}MB/{songsize}MB"
        self.updateGraph(bps)

    def start(self):
        copyfile(self.file, "./sharedmusic/"+os.path.basename(self.file))
        threading.Thread(
            target=self.parent.connect_frame.client.uploadSong, args=(self.file,)
        ).start()
        

    def onReceive(self):
        self.parent.log("The song has been uploaded!\nNow you can request it.", 
        "green")
        self.parent.resetStatusLabel()
        self.parent.log_frame.upload_btn.configure(
            state="normal",
            text="Upload"
        )
        self.destroy()

    def cancel(self):
        if not self.winfo_exists(): return
        self.parent.connect_frame.client.ft.stopUploading = True
        self.parent.connect_frame.client.ft.suicide()
        self.onCancel()

    def onCancel(self):
        self.parent.log("Upload has been canceled.", "red")
        self.parent.resetStatusLabel()
        self.parent.log_frame.upload_btn.configure(
            state="normal",
            text="Upload"
        )
        self.destroy()

    # /////CANVAS GRAPH//////
    def drawGraph(self):
        self.graph_canvas.delete("all")
        for i in range(self.canv_count+1):
            y = self.canv_h - i*15
            self.graph_canvas.create_line(0, y, self.canv_w+3, y, fill="#dbdbdb")
            self.graph_canvas.create_text(25, y, text=f"{int(round((i*15)*3.333))}kb/s", font=("Arial", 8))
    
    def updateGraph(self, bps):
        self.drawGraph()

        y = self.canv_h - bps//1024//3.3
        self.points.append(y)

        prevoriusXY = [50,self.canv_h]
        if len(self.points)>(self.canv_w+50)/25:
            self.points.pop(0)
            prevoriusXY = [50, y]

        for i, y in enumerate(self.points):
            x = i * 15 + 50
            self.graph_canvas.create_line(prevoriusXY[0], prevoriusXY[1], x,y, fill="blue", width=3)
            prevoriusXY = (x,y)

        self.graph_canvas.create_rectangle(prevoriusXY[0]-3, prevoriusXY[1]-3, prevoriusXY[0]+3, prevoriusXY[1]+3, fill="red", outline="red")

class MainApplication(Frame):
    def __init__(self, parent, *args, **kwargs) -> None:
        Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.ds_presence = DSPresence()
        self.cache = CacheManager()

        self.connect_frame = ConnectFrame(self, text="Connection")
        self.connect_frame.grid(row=0, column=0, padx=5, pady=5)

        self.log_frame = LogFrame(self, text="Logs")
        self.log = self.log_frame.insertTextLine
        self.log_frame.grid(row=0, column=1, padx=5, pady=5)

        self.connections_frame = ConnectionsFrame(self, text="Connections")
        self.connections_frame.grid(row=0, column=2, padx=5, pady=5)

        self.player_frame = PlayerFrame(self, text="PLAYER")
        self.player_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=10)

        self.mainstatus_label = Label(self, text="NETWORK IDLE")
        self.mainstatus_label.grid(row=2, columnspan=3, padx=5, pady=5)

    def resetAll(self):
        self.player_frame.stopTrack()
        self.connect_frame.setNormalState()
        self.log_frame.clearLogs()
        self.log_frame.upload_btn.configure(text="Upload", state="normal")
        self.connections_frame.clear()
        self.player_frame.status_label["text"] = "Waiting for the track..."
        self.resetStatusLabel()
        if self.log_frame.upload_win:self.log_frame.upload_win.cancel()

        root.focus()

    def setStatusLabel(self, text):
        self.mainstatus_label.configure(
            text=text,
            foreground="green"
        )

    def resetStatusLabel(self):
        self.mainstatus_label.configure(
            text="NETWORK IDLE",
            foreground="black"
        )

class DSPresence:
    def __init__(self):
        self.presence = None
        #self.connect()

    def connect(self):
        try:
            self.presence = Presence(889166597476982804)
            self.presence.connect()
            self.update("Not connected")
        except:
            pass

    def update(self, text, start_time=None):
        try:
            if start_time:
                self.presence.update(
                    pid=os.getpid(),
                    state=text,
                    large_image="mync",
                    large_text="Mync!",
                    start=start_time,
                    buttons=[{"label": "Get mync", "url":
                              "https://github.com/grishatop1/mync"}]
                )
            else:
                self.presence.update(
                    pid=os.getpid(),
                    state=text,
                    large_image="mync",
                    large_text="Mync!",
                    buttons=[{"label": "Get mync", "url":
                              "https://github.com/grishatop1/mync"}]
                )
        except:
            pass

def about(*args):
    '''Shows an About box'''
    messagebox.showinfo(title='About Mync',
                               message=
'''Mync - Music Sync
---------
Have a suggestion, found a typo or a bug, wanna just chat about the
program? Report the problem on the GitHub page (where you probably
got the program) at https://github.com/grishatop1/mync!
---------
''')

def unfocus(self, *args, **kwargs):
    root.focus()

if __name__ == "__main__":
    root = Tk()
    root.title("Mync Client")
    root.resizable(0,0)

    os.makedirs("sharedmusic/", exist_ok=True)

    pygame.mixer.init()

    app = MainApplication(root)
    app.pack(side="top", fill="both", expand=True)
    app.bind("<Button-1>", unfocus)

    root.bind("<F1>",about)
    menu = Menu(root)
    help_menu = Menu(menu, tearoff=0)
    menu.add_command(label='About', command=about, underline=0)
    root.config(menu=menu)

    root.mainloop()
