import time
import multiprocessing as mp
from modules.pypresence import Presence

class MyncPresence:
    def __init__(self, controller, pid) -> None:
        self.controller = controller
        self.pid = pid
        self.q = mp.Queue()
        self.p = mp.Process(target=self.process, args=(self.q,), daemon=True)
        self.p.start()

    def setConnected(self):
        self.q.put({"type": "setconnected"})

    def setDiscionnected(self):
        self.q.put({"type": "setdisconnected"})

    def setPlaying(self, songname, _time):
        self.q.put({
            "type": "playing",
            "songname": songname,
            "time": _time
        })

    def process(self, q):
        presence = Presence("889166597476982804")
        presence.connect()
        q.put({"type": "setdisconnected"}) #on start
        while True:
            time.sleep(3)
            response = q.get()
            if response["type"] == "setconnected":
                presence.update(
                    self.pid,
                    state="Awaiting a song...",
                    large_image="myncimage"
                )
            elif response["type"] == "setdisconnected":
                presence.update(
                    self.pid,
                    state="Not connected yet...",
                    large_image="myncimage"
                )
            elif response["type"] == "playing":
                _time = response["time"]
                songname = response["songname"]
                presence.update(
                    self.pid,
                    state=songname[:40],
                    large_image="myncimage",
                    start=_time
                )