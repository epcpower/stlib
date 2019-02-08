import json
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
from twisted.internet.task import LoopingCall
from typing import Callable


class WebSocketHandler():


    def __init__(self):
        self.topics: {str: str}
        self._callback: Callable[[str, dict], None]
        self.loopingCall: LoopingCall
        self.client: mqtt.Client = None
        self.topics: {str: str}


    def connect(self, url: str, client_id: str, topics: {str: str}, on_message: Callable[[str, dict], None]) -> None:
        """
        Makes WebSocket connection and starts looping
        :param url: str Websocket URL (starting with "wss://" and including path and all query parameters)
        :param client_id: str Client ID provided by AppSync
        :param topics: dict formatted as "topicstring": "created|updated|deleted"
        :param on_message: Callable that is called on every message. The first param is the action (created/updated/deleted)
        and the second is the file json object as a dict.
        """

        self._callback = on_message

        urlparts = urlparse(url)

        headers = {
            "Host": "{0:s}".format(urlparts.netloc),
        }

        self.client = mqtt.Client(client_id=client_id, transport="websockets")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.ws_set_options(path="{}?{}".format(urlparts.path, urlparts.query), headers=headers)
        self.client.tls_set()
        self.client.on_log = self._on_log

        # self.client.on_socket_open = lambda client, userdata, socket: print("Socket opened")
        # self.client.on_socket_close = lambda client, userdata, socket: print("Socket closed")

        self.client.connect(urlparts.netloc, port=443)
        self.topics = {topics[f]['topic']: f for f in topics}
        self.loopingCall: LoopingCall = LoopingCall(self.loop)
        self.loopingCall.start(1)

    def loop(self):
        if self.client is None:
            return

        # print("Looping")
        self.client.loop_read(5)
        self.client.loop_write()
        self.client.loop_misc()

    def disconnect(self):
        self.client.disconnect()
        self.client = None
        self.loopingCall.stop()

    def is_subscribed(self):
        return self.client is not None

    def _on_connect(self, client, userdata, flags, rc):
        print("[Graphql Websocket] On connect")
        for topic in self.topics:
            client.subscribe(topic)

    def _on_log(self, client, userdata, level, buf):
        print(f"[Graphql Websocket]  Log {level} {buf}")

    def _on_message(self, client, userdata, msg):
        action = self.topics.get(msg.topic)
        if action is None:
            return

        payload = msg.payload.decode('ascii')
        payload_json = json.loads(payload)
        print(f"[Graphql Websocket] Message received: {payload} -> {action}")

        # We *should* only get one payload, but just in case...
        for payload in payload_json['data'].values():
            self._callback(action, payload)




