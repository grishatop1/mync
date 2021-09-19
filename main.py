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

from shutil import copyfile
from transfer import Transfer
from pypresence import Presence

class Client:
    def __init__(self, app, ip, port, username):
        self.app = app
        self.addr = (ip,port)
        self.username = username
        self.s = socket.socket()

        self.force_disconnect = False
        self.alive = False
    
    def connect(self):
        try:
            self.s.settimeout(5)
            self.s.connect(self.addr)
            self.s.settimeout(None)
            self.alive = True
        except socket.error:
            self.app.connect_frame.setNormalState()
            showwarning("Connection", "Connection failed.")
            return
        except Exception as e:
            print(e)
            showerror("Client", "Maybe there is an error in the inputs. "+
                      "Check them and try again")
            return

        self.s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        self.t = Transfer(self.s)
        self.t.send(self.username.encode())
        connections = self.t.recvData()
        if connections == b"usernametaken":
            self.app.connect_frame.setNormalState()
            showwarning("Connection", "Username is already taken.")
            return
        users = pickle.loads(connections)
        self.t.send(b"gotall")

        threading.Thread(target=self.mainThread, daemon=True).start()

        self.app.connections_frame.addUsers(users)
        self.app.connect_frame.setConnectedState()
        showinfo("Connection", "Connected to the server!")

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
                self.app.player_frame.playTrack(songname)
                self.app.log(f"Playing {songname}", "green")
                continue

            data = pickle.loads(data)
            
            if data["method"] == "returnTracks":
                if self.app.log_frame.req_win:
                    self.app.log_frame.req_win.loadTracks(data["data"])
            
            elif data["method"] == "songrecvd":
                self.app.log_frame.upload_btn.configure(
                    state="normal",
                    text="Upload"
                )
                self.app.resetStatusLabel()
                self.app.log(
                    "The song has been uploaded! You can now request it",
                    "green")
                continue

            elif data["method"] == "checksong":
                songname = data["songname"]
                tracks = os.listdir("clientmusic/")
                if not songname in tracks:
                    self.t.sendDataPickle(
                        {"method": "reqsongfile", "songname": songname}
                    )
                    self.app.log("Missing song :(. Requesting it...", "red")
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
                with open("clientmusic/"+songname, "wb") as f:
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
                self.app.player_frame.playTrack(songname, start_time)
                self.app.log(f"Playing {songname}", "green")

        if not self.force_disconnect:
            self.alive = False
            self.s.close()
            self.app.resetAll()
            showerror("Connection", "Connection has been lost.")

    def uploadSong(self, path):
        songname = os.path.basename(path)
        with open(path, "rb") as f:
            song = f.read()
        self.t.sendDataPickle(
            {"method": "song",
            "songname": songname}
        )
        self.t.send(song)

    def getTracks(self):
        self.t.sendDataPickle({"method":"gettracks"})

    def reqSong(self, songname):
        self.t.sendDataPickle({"method": "req", "songname": songname}, blocking=False)

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

        #debug
        self.ip_entry.insert(0,"192.168.0.33:8888")
        self.username_entry.insert(0, "grisha")

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
        del self.client

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
        #self.log_entry = Entry(self, width=45)
        #self.log_entry.bind("<Return>", self.messageAction)

        self.log_text.tag_configure("green", foreground="green")
        self.log_text.tag_configure("red", foreground="red")
        self.log_text.tag_configure("black", foreground="black")

        self.upload_btn = Button(self, text="Upload",
                                 command=self.startUploadThread)
        self.req_btn = Button(self, text="Request a song",
                              command=self.startRequestWindow)

        self.log_text.grid(row=0, column=0, columnspan=2, padx=3, pady=3)
        self.upload_btn.grid(row=1, column=0, columnspan=1, pady=3)
        self.req_btn.grid(row=1, column=1, columnspan=1, pady=3)
        #self.log_entry.grid(row=2, column=0, columnspan=2, padx=3, pady=3)

    def startUploadThread(self):
        if not self.parent.connect_frame.client:
            return
        if not self.parent.connect_frame.client.alive:
            return

        root.focus()
        file = filedialog.askopenfilename(title="Open music file",
                                          filetypes=(("Music Files", "*.mp3"),))
        if not file: return

        copyfile(file, "clientmusic/"+os.path.basename(file))
        self.parent.setStatusLabel(f"Uploading {os.path.basename(file)}")
        self.parent.log(f"Uploading {os.path.basename(file)}")        
        self.upload_btn.config(state="disabled", text="Uploading...")
        threading.Thread(target=self.parent.connect_frame.client.uploadSong,
                         args=(file,)).start()

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
        


class ConnectionsFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.connections_listbox = Listbox(self)
        self.connections_listbox.pack(padx=3, pady=3)

    def addUser(self, username):
        self.connections_listbox.insert("end", username)

    def addUsers(self, connections):
        for username in connections:
            self.addUser(username)

    def removeUser(self, username):
        idx = self.connections_listbox.get(0, "end").index(username)
        self.connections_listbox.delete(idx)

    def clear(self):
        self.connections_listbox.delete(0, "end")


class PlayerFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.player = None
        self.start_time = 0

        self.status_label = Label(self, text="Waiting for the track...")
        self.volume_label = Label(self, text="Volume:")
        self.volume_var = IntVar()
        self.volume_scale = Scale(self, from_=0, to=100, 
                                    orient="horizontal",
                                    length=300,
                                    variable=self.volume_var)
        self.volume_scale.bind("<ButtonRelease-1>", self.setvolume)
        self.volume_var.set(100)

        self.status_label.grid(row=0, column=0, columnspan=2, padx=3, pady=3)
        self.volume_label.grid(row=1, column=0, padx=3, pady=3)
        self.volume_scale.grid(row=1, column=1, padx=3, pady=3)

    def playTrack(self, songname, start_time=0):
        pygame.mixer.music.load("clientmusic\\"+songname)
        pygame.mixer.music.play(start=start_time, loops=0)
        root.deiconify()
        root.title(f"Mync Client - Playing {songname}")
        self.status_label.configure(
            text=f"Playing {songname}",
            foreground="green"
        )
        self.parent.ds_presence.update(
            f"{os.path.splitext(songname)[0]}",
            time.time()
            )

    def stopTrack(self):
        pygame.mixer.music.stop()
        root.title("Mync Client")
        self.status_label.configure(
            text=f"Waiting for the track...",
            foreground="black"
        )

    def setvolume(self, event):
        pygame.mixer.music.set_volume(self.volume_var.get()/100)

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
        self.parent.connect_frame.client.getTracks()

    def loadTracks(self, tracks):
        self.tracks = tracks
        for track in tracks:
            self.tracks_list.insert("end", track)
        self.status_label["text"] = "Pick a song... (scrollable)"

    def play(self):
        songname = self.tracks_list.get(self.tracks_list.curselection())
        self.parent.connect_frame.client.reqSong(songname)
        self.destroy()

class MainApplicatin(Frame):
    def __init__(self, parent, *args, **kwargs) -> None:
        Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.ds_presence = DSPresence()

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
        self.connect()

    def connect(self):
        self.presence = Presence(889166597476982804)
        self.presence.connect()
        self.update("Not connected")

    def update(self, text, start_time=None):
        if start_time:
            self.presence.update(
                pid=os.getpid(),
                state=text,
                large_image="mync",
                large_text="Mync!",
                start=start_time,
                buttons=[{"label": "Get mync", "url": "https://github.com/grishatop1/mync"}]
            )
        else:
            self.presence.update(
                pid=os.getpid(),
                state=text,
                large_image="mync",
                large_text="Mync!",
                buttons=[{"label": "Get mync", "url": "https://github.com/grishatop1/mync"}]
            )

if __name__ == "__main__":
    root = Tk()
    root.title("Mync Client")
    root.resizable(0,0)

    app = MainApplicatin(root)
    app.pack(side="top", fill="both", expand=True)

    pygame.mixer.init()

    root.mainloop()
