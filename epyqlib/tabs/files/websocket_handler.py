import inspect
import json
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
from twisted.internet.defer import ensureDeferred
from twisted.internet.task import LoopingCall
from typing import Callable, Coroutine, List, Dict

SocketCloseHandler = Callable[[], Coroutine]
OnMessageHandler = Callable[[str, Dict], Coroutine]


class WebSocketHandler:
    def __init__(self):
        self._tag = "[Graphql Websocket]"
        self._on_message_handler: OnMessageHandler = None
        self._on_close_handler: SocketCloseHandler = None
        self.loopingCall: LoopingCall = None
        self.clients: List[mqtt.Client] = []
        self.disconnecting = False

        self.resubscribe = False

    def connect(
        self,
        response: Dict,
        on_message: Callable[[str, Dict], Coroutine],
        on_close: SocketCloseHandler = None,
    ) -> None:
        """
        Makes WebSocket connection and starts looping
        :param response JSON body response from a subscription call to AppSync
        :param on_message: Coroutine that is called on every message. The first param is the action (created/updated/deleted)
        and the second is the file json object as a dict.
        :param on_close: Coroutine that is called when any subscribed socket is closed.
        """
        self._on_message_handler = on_message
        self._on_close_handler = on_close

        new_subscriptions = response["extensions"]["subscription"]["newSubscriptions"]
        mqtt_connections = response["extensions"]["subscription"]["mqttConnections"]

        new_connections = {}
        for [action, details] in new_subscriptions.items():
            mqtt_connection = next(
                c for c in mqtt_connections if details["topic"] in c["topics"]
            )
            topic = details["topic"]

            if mqtt_connection["url"] not in new_connections:
                new_connections[mqtt_connection["url"]] = {
                    "connection": mqtt_connection,
                    "topics": set(),
                }

            new_connections[mqtt_connection["url"]]["topics"].add(topic)

        self._mqtt_connections = new_connections
        self._do_connect()

        self.resubscribe = True

        self.loopingCall: LoopingCall = LoopingCall(self.loop)
        self.loopingCall.start(1)

    def _do_connect(self):
        for connection in self._mqtt_connections.values():
            client_id = connection["connection"]["client"]
            url = connection["connection"]["url"]

            urlparts = urlparse(url)

            headers = {"Host": "{0:s}".format(urlparts.netloc)}

            client = mqtt.Client(client_id=client_id, transport="websockets")
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.on_log = self._on_log
            client.on_socket_close = self._on_socket_close

            client.ws_set_options(
                path="{}?{}".format(urlparts.path, urlparts.query), headers=headers
            )
            client.tls_set()

            client.user_data_set({"topics": connection["topics"]})

            client.connect(urlparts.netloc, port=443)
            self.clients.append(client)

    def loop(self):
        # if not self.is_subscribed():
        #     # If we shouldn't resub, stop looping
        #     if not self.resubscribe:
        #         self.loopingCall.stop()
        #         return
        #
        #     # Otherwise, re-sub
        #     self._do_connect()

        if len(self.clients) == 0:
            self.loopingCall.stop()

        for client in self.clients:
            client.loop_read()
            client.loop_write()
            client.loop_misc()

    def disconnect(self):
        self.resubscribe = False
        for client in self.clients:
            client.disconnect()

    def is_subscribed(self):
        return len(self.clients) > 0

    def _on_connect(self, client: mqtt.Client, userdata: Dict, flags, rc):
        topics: set[str] = userdata["topics"]
        sub_list = list(map(lambda topic: (topic, 1), topics))
        client.subscribe(sub_list)

    def _on_log(self, client, userdata, level, buf):
        print(f"{self._tag}  Log {level} {buf}")

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        try:
            payload = msg.payload.decode("ascii")
            payload_json = json.loads(payload)
            print(f"{self._tag} Message received: {payload}")
        except Exception as e:
            print(
                f"{self._tag} Error converting payload to JSON: "
                + msg.payload.decode("ascii")
            )
            print(e)
            return

        # We *should* only get one payload, but just in case...
        try:
            for action, payload in payload_json["data"].items():
                result = self._on_message_handler(action, payload)
                if inspect.iscoroutine(result):
                    ensureDeferred(result)
        except Exception as e:
            print(
                f"{self._tag} Error iterating over payload: " + json.dumps(payload_json)
            )
            print(e)

    def _on_socket_close(self, client: mqtt.Client, userdata: Dict, socket):
        if self.resubscribe:
            status = client.reconnect()
            if status == 0:
                return
            else:
                print(
                    f"{self._tag} Error reconnecting to websocket: {self.error_lookup[status]}. Aborting reconnect."
                )

        self.clients.remove(client)
        # print(f"Socket closed. Connection to topics ${userdata.get('topics')} closed.")
        # self.clients.remove(client)
        #
        # # Make sure this only fires once no matter how many clients are open
        # if self.disconnecting is False:
        #     self.disconnecting = True
        #     self.disconnect()
        #     self.disconnecting = False
        #
        #
        #     # Make sure the on_close handler only gets run once
        #     if self._on_close_handler:
        #         result = self._on_close_handler()
        #         if inspect.iscoroutine(result):
        #             ensureDeferred(result)

    # From https://pypi.org/project/paho-mqtt/#on-connect
    error_lookup = {
        mqtt.CONNACK_ACCEPTED: "Connection successful",
        mqtt.CONNACK_REFUSED_PROTOCOL_VERSION: "Connection refused - incorrect protocol version",
        mqtt.CONNACK_REFUSED_IDENTIFIER_REJECTED: "Connection refused - invalid client",
        mqtt.CONNACK_REFUSED_SERVER_UNAVAILABLE: "Connection refused - server unavailable",
        mqtt.CONNACK_REFUSED_BAD_USERNAME_PASSWORD: "Connection refused - bad username or password",
        mqtt.CONNACK_REFUSED_NOT_AUTHORIZED: "Connection refused - not authorised",
    }


# Example of the format of `response`:
# {
#   "extensions": {
#     "subscription": {
#       "mqttConnections": [
#         {
#           "url": "wss://a1yyia7sgxh08y-ats.iot.us-west-2.amazonaws.com/mqtt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA5..."
#           "topics": [
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/associationCreated/ad2fc514666b327b3e79f4255329988b30bfec23428bd62f7db900ffce4744a7",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/activityCreated/38c53ba841180e186aeaae8565e9807ddabb7becaf849cf336e24d1f23e2a12b",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileCreated/ad2fc514666b327b3e79f4255329988b30bfec23428bd62f7db900ffce4744a7"
#           ],
#           "client": "xtsaum2eyfhaxd2scqsjnajvmq"
#         },
#         {
#           "url": "wss://a1yyia7sgxh08y-ats.iot.us-west-2.amazonaws.com/mqtt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA5..."
#           "topics": [
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileUpdated/65a5e5608f9c9ce6e418848ef29015d110c059d1d02fb103288f5a7bab394e72",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/associationDeleted/65a5e5608f9c9ce6e418848ef29015d110c059d1d02fb103288f5a7bab394e72",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileUpdated/ad2fc514666b327b3e79f4255329988b30bfec23428bd62f7db900ffce4744a7"
#           ],
#           "client": "bqaskf7ddrfrnctwj4mf7fkwpi"
#         },
#         {
#           "url": "wss://a1yyia7sgxh08y-ats.iot.us-west-2.amazonaws.com/mqtt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA5..."
#           "topics": [
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileDeleted/129baf6c447f4da79303537da82ec8e71266c21536567ded0f5d997f75e889e3",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileDeleted/65a5e5608f9c9ce6e418848ef29015d110c059d1d02fb103288f5a7bab394e72",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/associationDeleted/ad2fc514666b327b3e79f4255329988b30bfec23428bd62f7db900ffce4744a7"
#           ],
#           "client": "y6myssziyffsvg7e4yfjjngaqy"
#         },
#         {
#           "url": "wss://a1yyia7sgxh08y-ats.iot.us-west-2.amazonaws.com/mqtt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA5..."
#           "topics": [
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileUpdated/",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/associationCreated/65a5e5608f9c9ce6e418848ef29015d110c059d1d02fb103288f5a7bab394e72",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileDeleted/"
#           ],
#           "client": "cbh5lbimwje2nawp42uwmp7o2e"
#         },
#         {
#           "url": "wss://a1yyia7sgxh08y-ats.iot.us-west-2.amazonaws.com/mqtt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA5..."
#           "topics": [
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileCreated/129baf6c447f4da79303537da82ec8e71266c21536567ded0f5d997f75e889e3",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileCreated/",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileDeleted/ad2fc514666b327b3e79f4255329988b30bfec23428bd62f7db900ffce4744a7"
#           ],
#           "client": "ollqguz5vvfn3jmyj5tsulz7su"
#         },
#         {
#           "url": "wss://a1yyia7sgxh08y-ats.iot.us-west-2.amazonaws.com/mqtt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA5..."
#           "topics": [
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileCreated/65a5e5608f9c9ce6e418848ef29015d110c059d1d02fb103288f5a7bab394e72",
#             "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileUpdated/129baf6c447f4da79303537da82ec8e71266c21536567ded0f5d997f75e889e3"
#           ],
#           "client": "tt7sop2eurffzhej45d4gu6ztm"
#         }
#       ],
#       "newSubscriptions": {
#         "activityCreated": {
#           "topic": "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/activityCreated/38c53ba841180e186aeaae8565e9807ddabb7becaf849cf336e24d1f23e2a12b",
#           "expireTime": 1553801051000
#         },
#         "fileUpdated": {
#           "topic": "674475255666/hmdhwjgyuja6nfrcb65tzc42vu/fileUpdated/",
#           "expireTime": 1553801051000
#         }
#       }
#     }
#   },
#   "data": {
#     "activityCreated": null,
#     "fileUpdated": null
#   }
# }
