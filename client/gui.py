import os
import sys
import threading

from tkinter import *
from tkinter import messagebox
from tkinter.ttk import *
from tkinter.messagebox import *
from tkinter import filedialog
from tkinter import Scale as ScaleDefault

from ttkbootstrap import Style

lng = None

class MainApplication(Tk):
    def __init__(self, controller, *args, **kwargs) -> None:
        Tk.__init__(self, *args, **kwargs)
        global lng

        self.controller = controller
        lng = self.controller.lng

        self.title(lng("title"))
        self.resizable(0,0)
        style = Style('material-dark', "media/themes.json")
        style.colors.set("primary", "#BB86FC")        
        self.iconbitmap("media/iconica.ico")

        self.top = TopLevelControl(self)

        self.bind("<F1>",self.about)
        self.menu = Menu(self)
        self.help_menu = Menu(self.menu, tearoff=0)
        self.help_menu.add_command(label=lng("about_menu"),command=self.about,underline=0)
        self.help_menu.add_command(label=lng("license"),command=self.license,underline=0)
        self.lang_menu = Menu(self.menu, tearoff=0)
        self.lang_menu.add_command(label='English',command=lambda:self.changeLang("en"),underline=0)
        self.lang_menu.add_command(label='Srpski',command=lambda:self.changeLang("sr"),underline=0)
        self.lang_menu.add_command(label='日本語',command=lambda:self.changeLang("jp"))
        self.lang_menu.add_command(label='Русский',command=lambda:self.changeLang("ru"),underline=0)
        self.menu.add_cascade(label=lng("language_menu"), menu=self.lang_menu, underline=0)
        self.menu.add_cascade(label=lng("help_menu"), menu=self.help_menu, underline=0)
        self.config(menu=self.menu)

        self.connect_frame = ConnectFrame(self, text=lng("connection"))
        self.connect_frame.grid(row=0, column=0, padx=5, pady=5)

        self.log_frame = LogFrame(self, text=lng("logs"))
        self.log = self.log_frame.insertTextLine
        self.log_frame.grid(row=0, column=1, padx=5, pady=5)

        self.connections_frame = ConnectionsFrame(self, text=lng("connections"))
        self.connections_frame.grid(row=0, column=2, padx=5, pady=5)

        self.player_frame = PlayerFrame(self, text=lng("player"))
        self.player_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=10)

        self.netstatus_label = NetworkStatusLabel(self)
        self.netstatus_label.grid(row=2, columnspan=3, padx=5, pady=5)

    def changeLang(self, lang_code):
        if askyesno("Mync", lng("wanna-restart")):
            lng.changeLanguage(lang_code)
            os.execl(sys.executable, sys.executable, *sys.argv)

    def showDialog(self, message, title="Mync Client", _type="info"):
        if _type == "info":
            showinfo(title, message)
        elif _type == "warning":
            showwarning(title, message)
        else:
            showerror(title, message)

    def about(*args):
        messagebox.showinfo(title=lng("about_menu"),message=lng("about_info"))

    def license(*args):
        messagebox.showinfo(title=lng("license"),message=lng("license_text"))

class TopLevelControl:
    def __init__(self, parent) -> None:
        self.parent = parent

        self.req_win = None
        self.upload_win = None

    def checkClient(self):
        return self.parent.controller.isClientAlive()

    def openRequestWindow(self):
        if not self.checkClient(): return
        if self.req_win: return
        self.req_win = RequestTopLevel(self.parent)

    def closeRequestWindow(self):
        if not self.req_win: return
        self.req_win.close()
        self.req_win = None

    def openUploadWindow(self):
        if not self.checkClient(): return
        if self.upload_win: return

        filepath = filedialog.askopenfilename(title="Open music file",
                        filetypes=(("Music Files","*.mp3"),))
        if not filepath: return
        self.upload_win = UploadTopLevel(self.parent, filepath)

    def closeUploadWindow(self):
        if not self.upload_win: return
        self.upload_win.close()
        self.upload_win = None

    def loadTracksInReq(self, tracks):
        if not self.req_win: return
        self.req_win.loadTracks(tracks)

class ConnectFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.client = None

        self.username_label = Label(self, text=lng("username"))
        self.username_entry = Entry(self)
        self.ip_label = Label(self, text=lng("server_ip"))
        self.ip_entry = Entry(self)
        self.connect_btn = Button(self, 
            text=lng("connect"), 
            command=self.connectCommand
        )

        self.username_label.grid(row=1, column=0, padx=3, pady=3)
        self.username_entry.grid(row=1, column=1, padx=3, pady=3)
        self.ip_label.grid(row=2, column=0, padx=3, pady=3)
        self.ip_entry.grid(row=2, column=1, padx=3, pady=3)
        self.connect_btn.grid(row=3, column=0, columnspan=2, padx=3, pady=3)

        self.loadCache()

    def loadCache(self):
        ip = self.parent.controller.cache.read("ip")
        username = self.parent.controller.cache.read("username")
        self.ip_entry.insert(0, ip)
        self.username_entry.insert(0, username)
        
    def connectCommand(self):        
        try:
            ip, port = self.ip_entry.get().split(":")
            port = int(port)
        except: return
        username = self.username_entry.get()
        if not username: return

        self.setConnectingState()
        threading.Thread(
            target=self.parent.controller.createClientInstance,
            args=(ip, port, username),
            daemon=True
        ).start()

    def disconnectCommand(self):
        self.parent.controller.removeClientInstance()
        self.setNormalState()
        self.parent.showDialog(lng("disconnected"), "Connection")

    def setConnectingState(self):
        self.username_entry["state"] = "disabled"
        self.ip_entry["state"] = "disabled"
        self.connect_btn.config(
            text=lng("connecting"),
            state="disabled"
        )

    def setNormalState(self):
        self.username_entry["state"] = "normal"
        self.ip_entry["state"] = "normal"
        self.connect_btn.config(
            text=lng("connect"),
            state="normal",
            command=self.connectCommand
        )

    def setConnectedState(self, dialog=True):
        self.username_entry["state"] = "disabled"
        self.ip_entry["state"] = "disabled"
        self.connect_btn.config(
            text=lng("disconnect"),
            state="normal",
            command=self.disconnectCommand
        )
        if dialog:
            showinfo("Connection", lng("connected"))

class LogFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.log_text = Text(self, width=50, height=10, state="disabled")

        colors = ["green", "red", "blue", "black", "orange", "#d97000"]
        for color in colors:
            self.log_text.tag_configure(color, foreground=color)

        self.upload_btn = Button(self, text=lng("upload"),
            command=self.openUploadCommand
        )
        self.req_btn = Button(self, text=lng("request"), 
            command=self.openRequestCommand
        )

        self.log_text.grid(row=1, column=0, columnspan=2, padx=3, pady=3)
        self.upload_btn.grid(row=0, column=0, columnspan=1, pady=3)
        self.req_btn.grid(row=0, column=1, columnspan=1, pady=3)

        self.chat_subframe = ChatSubFrame(self)
        self.chat_subframe.grid(row=2, column=0, columnspan=2)

    def insertTextLine(self, data, color="black"):
        self.log_text["state"] = "normal"
        self.log_text.insert("end", data + "\n", color)
        self.log_text["state"] = "disabled"
        self.log_text.see("end")

    def clearLogs(self):
        self.log_text["state"] = "normal"
        self.log_text.delete("1.0", "end")
        self.log_text["state"] = "disabled"

    def openRequestCommand(self):
        self.parent.top.openRequestWindow()

    def openUploadCommand(self):
        self.parent.top.openUploadWindow()

        
class ChatSubFrame(Frame):
    def __init__(self, parent, *args, **kwargs) -> None:
        Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        
        self.input = PlaceholderEntry(
            self,
            lng("chat_placeholder"),
            style="TEntry",
            placeholder_style="Placeholder.TEntry",
            width=36,
        )
        self.input.bind("<Return>", self.sendMsg)
        self.send_btn = Button(self, 
            text=lng("chat_send"),
            command=self.sendMsg, width=7
        )

        self.input.grid(row=0, column=0, padx=3, pady=3, ipady=1, sticky="we")
        self.send_btn.grid(row=0, column=1, padx=3, pady=3, sticky="e")

    def sendMsg(self, *args):
        msg = self.input.get().strip(' ')
        if not msg: return
        if self.input["foreground"] == "gray": return
        self.input.focus()
        self.input.delete(0, "end")
        self.parent.parent.controller.sendMessage(msg)

class ConnectionsFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.connections_listbox = Listbox(self, width=30)
        self.connections_listbox.pack(padx=3, pady=3)

        self.clients = {}
        # {"username" : ""} <- suffix

    def addUser(self, username, suffix="", idx=None):
        self.clients[username] = suffix
        self.connections_listbox.insert(
            "end" if not idx else idx, username + suffix
        )

    def addUsers(self, connections):
        for username, suffix in connections.items():
            self.addUser(username, suffix)

    def changeSuffix(self, username, new_suffix):
        suffix = self.clients[username]
        idx = self.removeUser(username)
        self.addUser(username, new_suffix, idx)

    def removeUser(self, username):
        suffix = self.clients[username]
        idx = self.connections_listbox.get(0, "end").index(username + suffix)
        self.connections_listbox.delete(idx)
        del self.clients[username]
        return idx

    def clear(self):
        self.connections_listbox.delete(0, "end")


class PlayerFrame(LabelFrame):
    def __init__(self, parent, *args, **kwargs) -> None:
        LabelFrame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.player = None
        self.start_time = 0

        self.status_label = Label(self, text=lng("waiting"))
        self.volume_label = Label(self, text=lng("volume"))
        self.volume_var = IntVar()
        self.volume_scale = ScaleDefault(self, from_=0, to=100, 
                                    orient="horizontal",
                                    length=300,
                                    variable=self.volume_var)
        self.volume_scale.bind("<B1-Motion>", self.changeVolume)

        self.status_label.grid(row=0, column=0, columnspan=2, padx=3, pady=3)
        self.volume_label.grid(row=1, column=0, padx=3, pady=3)
        self.volume_scale.grid(row=1, column=1, padx=3, pady=3)

        self.volume_var.set(self.parent.controller.player.loadCacheVolume())
        self.changeVolume()
        

    def changeVolume(self, *args):
        volume = self.volume_var.get()
        self.parent.controller.player.setVolume(volume)

    def setPlayingState(self, songname):
        self.status_label["text"] = lng("player-playing", songname)
        self.status_label["foreground"] = "#c89cff"

    def resetState(self):
        self.status_label["text"] = lng("waiting")
        self.status_label["foreground"] = "white"

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
        self.grab_set() #get the all controls from root muahaha
        self.bind("<Return>", self.playCommand)
        self.protocol("WM_DELETE_WINDOW", self.exit)

        self.tracks = []
        
        self.status_label = Label(self,
            text=lng("upl_loading")
        )
        self.search_entry = PlaceholderEntry(
            self,
            lng("req_search"),
            style="TEntry",
            placeholder_style="Placeholder.TEntry",
            width=70
        )
        self.tracks_list = Listbox(self, width=100)
        self.choose_btn = Button(self, text=lng("req_play"), command=self.playCommand)

        self.search_entry.bind("<KeyRelease>", self.search)

        self.status_label.pack(padx=5, pady=5)
        self.search_entry.pack(padx=5, pady=5)
        self.tracks_list.pack(padx=5, pady=5)
        self.choose_btn.pack(padx=5, pady=10)

        self.parent.controller.requestTracksForReq()

    def exit(self):
        self.parent.top.closeRequestWindow()

    def playCommand(self, *args):
        try:
            songname = self.tracks_list.get(self.tracks_list.curselection())
        except:
            return
        self.parent.controller.sendPlaytrackRequest(songname)

    def loadTracks(self, tracks):
        try:
            self.tracks = tracks
            for track in tracks:
                self.tracks_list.insert("end", track)
            self.status_label["text"] = lng("req_pick")
        except:pass

    def search(self, *args):
        srch = self.search_entry.get()
        if not srch or self.search_entry["foreground"] == "gray":
            self.reloadTracks()
            return
        
        closest = []
        for song in self.tracks:
            if srch.lower() in song.lower():
                closest.append(song)

        self.tracks_list.delete(0, "end")
        for item in closest:
            self.tracks_list.insert(END, item)

        self.tracks_list.select_set(0)

    def reloadTracks(self):
        self.tracks_list.delete(0, "end")
        for track in self.tracks:
            self.tracks_list.insert("end", track)

    def close(self):
        self.destroy()

class UploadTopLevel(Toplevel):
    def __init__(self, parent, filepath, *args, **kwargs) -> None:
        Toplevel.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.filesize = os.path.getsize(filepath)

        self.title("Upload Window")
        self.resizable(0,0)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.canv_w = 300
        self.canv_h = 80
        self.canv_count = self.canv_h//15
        self.points = []

        self.title_label = Label(self, text=lng("upl_uploading", self.filename[:25]))
        self.graph_canvas = Canvas(self, width=self.canv_w, height=self.canv_h, background="white")
        self.speed_label = Label(self, text=lng("upl_loading"))
        self.percent_label = Label(self, text=lng("upl_loading"))
        self.cancel_btn = Button(self, text=lng("upl_cancel"), command=self.cancel)

        self.title_label.grid(row=0, column=0, columnspan=2, pady=(10,0))
        self.graph_canvas.grid(row=1, column=0, columnspan=2, padx=15, pady=8)
        self.speed_label.grid(row=2, column=0, padx=3, pady=3)
        self.percent_label.grid(row=2, column=1, padx=3, pady=3)
        self.cancel_btn.grid(row=3, column=0, columnspan=2, padx=3, pady=3)

        self.drawGraph()
        self.start()

    def start(self):
        self.parent.controller.startUploading(self.filepath)

    def updateStatus(self, bps, received):
        songsize = round(self.filesize/1024/1024, 1)
        self.speed_label["text"] = lng("upl_flow", round(bps/1024, 1))
        self.percent_label["text"] = lng("upl_sent", round(received/1024/1024, 1), songsize)
        self.updateGraph(bps)

    def cancel(self):
        self.parent.controller.cancelUpload()

    def close(self):
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

class NetworkStatusLabel(Label):
    def __init__(self, parent, *args, **kwargs) -> None:
        Label.__init__(self, parent, text=lng("netw_idle"), foreground="white")
        self.parent = parent

    def set(self, text):
        self["text"] = text
        self["foreground"] = "#c89cff"

    def reset(self):
        self["text"] = lng("netw_idle")
        self["foreground"] = "white"
