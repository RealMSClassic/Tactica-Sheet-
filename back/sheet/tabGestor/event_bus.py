# ./back/sheet/gestor/event_bus.py
from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)

    def subscribe(self, topic: str, fn):
        if callable(fn):
            self._subs[topic].append(fn)

    def publish(self, topic: str, data=None):
        for fn in list(self._subs.get(topic, [])):
            try:
                fn(data)
            except Exception as ex:
                print(f"[BUS:{topic}] listener error:", ex)

class _NoBus:
    def subscribe(self, *_, **__): pass
    def publish(self, *_, **__): pass
