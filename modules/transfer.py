import socket
import threading
import queue
import pickle
import time

class MyncTransfer:
    def __init__(self, sock):
        self.s = sock
        self.header_len = 8 #about 95MB
        self.pending = queue.Queue()
        self.buffer = 2048
        threading.Thread(target=self.sendDataLoop, daemon=True).start()

    def _pad(self, data:bytes, to:int):
        return data + b" " * (to - len(data) % to)

    def attachHeader(self, data):
        header = self._pad(str(len(data)).encode(), self.header_len)
        return header + data

    def send(self, data):
        packet = self.attachHeader(data)
        lock = queue.SimpleQueue()
        self.pending.put(
            [lock, packet]
        )
        lock.get()
    
    def sendPickle(self, obj):
        data = pickle.dumps(obj)
        self.send(data)

    def sendNow(self, data):
        packet = self.attachHeader(data)
        self.s.send(packet)

    def sendDataLoop(self):
        while True:
            lock, data = self.pending.get()
            try:
                self.s.send(data)
                lock.put(1)
            except socket.error:
                return

    def recvData(self):
        data = b""
        toRecv = self.header_len
        header = b""
        recvd = 0

        while True:
            try:
                header += self.s.recv(toRecv)
            except: return
            if not header: return
            if len(header) == self.header_len:
                header_len = int(header)
                break
            toRecv -= len(header) #very unlikely to happen
        
        while True:
            try:
                packet = self.s.recv(self.buffer)
            except: return
            if not packet: return
            recvd += len(packet)
            data += packet
            if recvd == header_len:
                break

        return data