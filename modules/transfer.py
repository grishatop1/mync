import socket
import threading
import queue
import pickle
import time

class Transfer:
	def __init__(self, sock):
		self.s = sock
		self.pending = queue.Queue()
		self.header = 12
		self.buffer = 1024 * 2
		self.timeout = 5
		self.total = 0
		threading.Thread(target=self.sendDataLoop, daemon=True).start()

	def appendHeader(self, data):
		data_len = len(data)
		header = str(data_len).encode() + (self.header - len(str(data_len))) * b" "
		return header + data

	def send(self, data, blocking=True):
		h_data = self.appendHeader(data)
		if blocking:
			lock = queue.Queue()
			self.pending.put([lock, h_data])
			result = lock.get()
			return result
		else:
			self.pending.put([None, h_data])

	def sendDataPickle(self, obj, blocking=True):
		data = pickle.dumps(obj)
		self.send(data, blocking)

	def sendDataLoop(self):
		while True:
			lock, data = self.pending.get()
			try:
				self.s.send(data)
				if lock:
					lock.put(True)
			except socket.error:
				return

	def recvData(self):
		full = b""
		recv_len = 0
		recv_size = self.header
		header = b""
		new = True
		while True:
			if recv_size == 0:
				break
			try:
				data = self.s.recv(recv_size)
			except socket.error:
				return
			if not data:
				return

			if new:
				header += data
				if len(header) < self.header:
					recv_size = self.header - len(header)
					continue
				try:					
					actual_len = int(header)
				except:
					return
				recv_size = min(actual_len, self.buffer)
				new = False
				continue

			full += data
			recv_len += len(data)
			recv_size = min(actual_len - recv_len, self.buffer)

			self.total = int((recv_len/actual_len)*100)

		self.total = 100
		return full