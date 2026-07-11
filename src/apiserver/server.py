from tornado.web import Application, RequestHandler
from tornado.websocket import WebSocketHandler
from tornado.ioloop import IOLoop, PeriodicCallback
import json
from datetime import datetime, timedelta
import pandas as pd


class MyWebSocketHandler(WebSocketHandler):
    
    def __init__(self, application, request):
        super().__init__(application, request)
        self.connections = set()
        
        self.periodic_callback = PeriodicCallback(self.sim, 10000)
    
    def open(self, *args: str, **kwargs: str):
        self.connections.add(self)
        print("New webSocket opened.")
        self.write_message("New webSocket connection established.")
        return super().open(*args, **kwargs)
    
    def on_message(self, message: str | bytes):
        return super().on_message(message)
    
    def on_close(self) -> None:
        self.connections.remove(self)
        print("WebSocket closed.")
    
    def check_origin(self, origin: str):
        return True
    
    def sim(self):
        pass
