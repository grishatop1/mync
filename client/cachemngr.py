import os
import sys
import pickle

class CacheManager:
    def __init__(self):
        self.generatePaths()
        self._checkInitial()

    def _checkInitial(self):
        #checks if program was started for the first time
        if not os.path.exists(self.cache_file):
            self._check()
            data = {
                "volume": 80,
                "ip": "",
                "username": "",
                "language": "en"
            }
            with open(self.cache_file, "wb") as f:
                pickle.dump(data, f)
    
    def _check(self):
        os.makedirs(self.cache_path, exist_ok=True)
        os.makedirs(self.sharedmusic, exist_ok=True)
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

    def generatePaths(self):
        if sys.platform == "win32":
            self.appdata = os.getenv('APPDATA').replace("\\", "/")
            self.cache_path = self.appdata+"/.mync/"
            self.cache_file = self.cache_path+"cache.temp"
            self.sharedmusic = self.cache_path+"sharedmusic/"
        elif sys.platform == "linux":
            self.appdata = "cache"
            self.cache_path = self.appdata+"/.mync/"
            self.cache_file = self.cache_path+"cache.temp"
            self.sharedmusic = self.cache_path+"sharedmusic/"