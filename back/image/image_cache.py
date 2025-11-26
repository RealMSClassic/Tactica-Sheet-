# ./back/image/image_cache.py
from __future__ import annotations
import os, time, base64, hashlib
from typing import Optional

class ImageCache:
    def __init__(self, cache_dir: str = "images_cache", ttl_seconds: int = 3600, max_items: int = 1000):
        self.cache_dir = cache_dir
        self.ttl = ttl_seconds
        self.max_items = max_items
        self.mem = {}       # recid -> (ts, b64)
        self.order = []     # LRU order
        os.makedirs(self.cache_dir, exist_ok=True)

    # ----- L1: memoria -----
    def get_b64(self, recid: str) -> Optional[str]:
        if not recid: return None
        item = self.mem.get(recid)
        now = time.time()
        if item and (now - item[0] < self.ttl):
            # refresh LRU
            try: self.order.remove(recid)
            except ValueError: pass
            self.order.append(recid)
            return item[1]
        # L2: disco
        path = self._path(recid)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode("utf-8")
                self._set_mem(recid, b64)
                return b64
            except Exception:
                return None
        return None

    def set_b64(self, recid: str, b64: str) -> None:
        self._set_mem(recid, b64)
        try:
            data = base64.b64decode(b64)
            with open(self._path(recid), "wb") as f:
                f.write(data)
        except Exception:
            # si no se pudo escribir, al menos queda en RAM
            pass

    def _set_mem(self, recid: str, b64: str):
        now = time.time()
        self.mem[recid] = (now, b64)
        try: self.order.remove(recid)
        except ValueError: pass
        self.order.append(recid)
        # LRU trim
        while len(self.order) > self.max_items:
            old = self.order.pop(0)
            self.mem.pop(old, None)

    def _path(self, recid: str) -> str:
        # nombre estable y seguro
        safe = hashlib.sha1(recid.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{safe}.jpg")
