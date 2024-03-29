#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import json
import uldlib.const as constants
import base64
import hashlib
import socket
import uuid
from threading import Thread
from typing import List

from uldlib.torrunner import TOR_CONFIG
from uldllocalhost import Settings, WebFrontend, HTTPRequest, HTTPResponse, Downloader

# Delete the log from torrunner, since it's not needed I think
# And it also does bad stuff in this library folder
if TOR_CONFIG.get('Log', 666) != 666:
    del TOR_CONFIG['Log']


class WebSocketFrame:
    def __init__(self, fin=False, rsv=0, opcode=0, hasMask=False, maskingKey=bytes([]), payloadData=bytes([])):
        self.fin = fin
        self.rsv = rsv
        self.opcode = opcode
        self.hasMask = hasMask
        self.maskingKey = maskingKey
        self.payloadData = payloadData

    def __str__(self):
        return f"<Frame: {self.opcode} containing {self.payloadData}>"

    def __groupString(self, string, n):
        return [string[i:i + n] for i in range(0, len(string), n)]

    def __listToLenBeginWith(self, oldList, length, beginWith):
        newList = list(map(lambda a: beginWith, list(range(length - len(oldList)))))
        newList.extend(oldList)
        return newList

    def __mask(self, payloadData, maskingKey):
        return bytes(map(lambda a: a[1] ^ maskingKey[a[0] % len(maskingKey)], enumerate(payloadData)))

    def create(self):
        # https://www.rfc-editor.org/rfc/rfc6455#section-5.2
        binaryInts = []
        firstByte = 0
        if self.fin:
            firstByte |= (1 << 7)
        firstByte += (self.rsv << 3)
        firstByte += self.opcode
        binaryInts.append(firstByte)
        lengthByte = 0
        length = len(self.payloadData)
        hexPart = hex(length)[2:]
        if len(hexPart) % 2:
            hexPart = "0" + hexPart
        lengthBytes = list(map(lambda hexStr: int(hexStr, 16), self.__groupString(hexPart, 2)))
        if self.hasMask:
            lengthByte |= (1 << 7)
        extendedLengthBytes = []
        if length > 125:
            if length >= 65536:
                lengthByte += 127
                lengthBytes = self.__listToLenBeginWith(lengthBytes, 4, 0)
            else:
                lengthByte += 126
                lengthBytes = self.__listToLenBeginWith(lengthBytes, 2, 0)
            extendedLengthBytes.extend(lengthBytes)
        else:
            lengthByte += length
        binaryInts.append(lengthByte)
        binaryInts.extend(extendedLengthBytes)
        if self.hasMask:
            binaryInts.extend(self.maskingKey)
            binaryInts.extend(self.__mask(self.payloadData, self.maskingKey))
        else:
            binaryInts.extend(self.payloadData)
        return bytes(binaryInts)


class ServerConnection:
    def __init__(self, conn: socket.socket, addr: str, id: uuid.UUID, server, captures=False, debug_print=False):
        self.conn = conn
        self.addr = addr
        self.id = id
        self.server = server
        self.webFrontend: WebFrontend | None = None
        self.captures = captures
        self.debug_print = debug_print

        self.__apiHandler = False
        self.__alive = True
        self.__responseThread = Thread(target=self.__responseProcessor)  # Receive data from client, always runs
        self.__requestThread = Thread(
            target=self.__requestProcessor)  # Send data to client, start only if we have request
        self.__requests = []

        self.__downloader = None  # Used only in some connections!
        self.__downloaderRunThread = None  # Used only in some connections!

        self.__responseThread.start()

    def print(self, *args, sep=' ', end='\n', file=None):
        if self.debug_print:
            print(*args, sep=sep, end=end, file=file)

    # byte & numb is 1
    # 0110 & 100 is 1
    # 0110 & 1000 is 0
    @staticmethod
    def __bit(byte: int, numb: int):
        return int((byte & numb) == numb)

    @staticmethod
    def __serveFile(fileName: str):
        # self.print(f"Serving file: {fileName}")
        response = HTTPResponse()
        response.setStatusCode(200).setReasonPhrase("OK")
        with open(fileName, "rb+") as f:
            response.setBody(f.read())
        return response

    def __sendWebSocketJSON(self, obj: dict):
        webSocket = WebSocketFrame(fin=True, opcode=0x1, payloadData=bytes("json" + json.dumps(obj), 'utf-8'))
        self.__addWebSocketRequest([webSocket])

    @staticmethod
    def __readSettings() -> Settings:
        raw: dict = json.load(open("settings.json", "r+"))
        settings = Settings()

        settings.urls = raw.get("urls", [])

        main = raw.get("main", {})
        settings.parts = main.get('parts', 20)
        settings.password = main.get("password", "")
        settings.output = main.get('output', "./")
        settings.temp = main.get('temp', "./")
        settings.yes = main.get('overwrite', False)

        log = raw.get("log", {})
        settings.parts_progress = log.get('partsProgress', False)
        settings.log = log.get("log", "")
        # Nope, you can't select frontend - BECAUSE THIS IMPLEMENTS THE WEB FRONTEND

        captcha = raw.get("captcha", {})
        settings.auto_captcha = captcha.get('autoCaptcha', False)
        settings.manual_captcha = captcha.get('manualCaptcha', False)

        tor = raw.get("tor", {})
        settings.enforce_tor = tor.get('enforceTor', False)
        settings.conn_timeout = tor.get('connTimeout', constants.DEFAULT_CONN_TIMEOUT)

        # Ensure the defaults are written
        ServerConnection.__writeSettings(settings)
        return settings

    @staticmethod
    def __writeSettings(settings: Settings):
        raw = {
            'urls': settings.urls,
            'main': {'parts': settings.parts, 'password': settings.password, 'output': settings.output,
                     'temp': settings.temp, 'overwrite': settings.yes},
            'log': {'partsProgress': settings.parts_progress, 'log': settings.log},
            'captcha': {'autoCaptcha': settings.auto_captcha, 'manualCaptcha': settings.manual_captcha},
            'tor': {'enforceTor': settings.enforce_tor, 'connTimeout': settings.conn_timeout}
        }
        json.dump(raw, open("settings.json", "w+"))

    def __handleAPIMessage(self, id: uuid.UUID, messageFrames: List[WebSocketFrame], connection: socket.socket):
        # self.print(f"({id}) Received message: {list(map(lambda frame: str(frame), messageFrames))}")
        opcode = None
        payloads = []
        for frame in messageFrames:
            if not opcode:
                opcode = frame.opcode
                if opcode not in [0x1, 0x2, 0x8, 0x9, 0xA]:
                    raise RuntimeError(f"Received wrong message beginning frame opcode {opcode}.")
            else:
                if frame.opcode != 0x0:
                    raise RuntimeError(f"Received wrong continuation frame opcode {frame.opcode}.")
            payloads.append(frame.payloadData)
        payload: str | bytes | dict = bytes([]).join(payloads)
        if opcode == 0x1:  # Denotes a text frame
            payload = payload.decode('utf-8')
            if payload.startswith("json"):
                payload = json.loads(payload[4:])
            self.print(f"We received message: {payload}")
            if isinstance(payload, str):
                if payload == "Hello":
                    self.__sendWebSocketJSON({'type': "Hi"})
            else:
                self.print("Received json!")
                try:
                    if payload['type'] == "request":
                        if payload['request'] == "settings":
                            self.__sendWebSocketJSON({'type': "response",
                                                      'source': payload,
                                                      'settings': json.load(open("settings.json", "r+"))})
                        elif payload['request'] == "constants":
                            isBad = lambda k: k.startswith('__')
                            consts = {k: v for k, v in vars(constants).items() if not isBad(k)}
                            self.__sendWebSocketJSON({'type': "response",
                                                      'source': payload,
                                                      'constants': consts})
                    elif payload['type'] == "save":
                        if payload['save'] == "settings":
                            json.dump(payload['settings'], open("settings.json", "w+"))
                            self.__sendWebSocketJSON({'type': "saved",
                                                      'source': payload,
                                                      'settings': payload['settings']})
                    elif payload['type'] == "download":
                        if payload['download'] == "start":
                            # Start downloading
                            settings = self.__readSettings()
                            self.__downloaderRunThread = Thread(target=self.__downloader.run,
                                                                args=(settings,))
                            self.__downloaderRunThread.start()
                            self.__sendWebSocketJSON({'type': "download",
                                                      'source': payload,
                                                      'download': self.__downloader.getState()})
                        elif payload['download'] == "state":
                            self.__sendWebSocketJSON({'type': "state",
                                                      'source': payload,
                                                      'state': self.__downloader.getState()})
                        elif payload['download'] == "stop":
                            if self.__downloader.exitHandler:
                                self.__downloader.exitHandler()
                        else:
                            self.print("Undefined payload JSON:", payload)
                    elif payload['type'] == "promptResponse":
                        if self.webFrontend and self.webFrontend.prompts.get(payload['id'], 666) != 666:
                            self.webFrontend.prompts[payload['id']] = payload['promptResponse']
                    else:
                        self.print("Undefined payload JSON:", payload)
                except KeyError:
                    self.print("KeyError")
        elif opcode == 0x2:  # Denotes a binary frame
            self.print(f"We received binary: {payload}")
        elif opcode == 0x8:  # Denotes a connection close
            connection.close()
        elif opcode == 0x9:  # Denotes a ping
            self.print("We were pinged!")
        elif opcode == 0xA:  # Denotes a pong
            self.print("We received pong!")
        else:
            raise RuntimeError("Wtf?!")

    def __addRequest(self, type: str, data: str | dict):
        request = {
            'type': type,
            'response': None,
            'closed': False
        }
        for key in data:
            request[key] = data[key]
        self.__requests.append(request)
        if self.__alive and not self.__requestThread.is_alive():
            self.__requestThread.start()

    def __addWebSocketRequest(self, webSockets: List[WebSocketFrame]):
        self.__addRequest("websocket", {'webSockets': webSockets})

    def __responseProcessor(self):
        conn = self.conn
        id = self.id

        allData = b''
        i = 0
        path = None
        try:
            while self.__alive:
                data = conn.recv(1024 * 8)
                if not data:
                    break
                allData += data
                # self.print(data)
                if i == 0:  # Don't exit on second request
                    request = HTTPRequest(data)
                    requestURI = request.requestURI.decode('ascii')
                    if request.getHeader(bytes("Host", 'ascii')) is None:
                        if self.server.host == "127.0.0.1" and requestURI.startswith(f"localhost:{self.server.port}"):
                            path = requestURI[len(f"localhost:{self.server.port}"):]
                        elif requestURI.startswith(f"{self.server.host}:{self.server.port}"):
                            path = requestURI[len(f"{self.server.host}:{self.server.port}"):]
                        else:
                            raise RuntimeError("Oh no.")
                    else:
                        path = requestURI
                    if path == "/api":
                        self.__apiHandler = True
                        self.__downloader = Downloader(self)
                        sha1 = hashlib.sha1()
                        hashedText = request.getHeader(bytes("Sec-WebSocket-Key", 'ascii')).decode(
                            'ascii') + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                        sha1.update(bytes(hashedText, 'ascii'))
                        # self.print("Hashed:", sha1.digest(), f"===> {base64.b64encode(sha1.digest()).decode('ascii')}")
                        # f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {base64.b64encode(sha1.digest()).decode('ascii')}\r\n\r\n",
                        response = HTTPResponse()
                        response.setStatusCode(101).setReasonPhrase("Switching Protocols")
                        response.addHeader("Upgrade", "websocket").addHeader("Connection", "Upgrade")
                        response.addHeader("Access-Control-Allow-Origin",
                                           "*")  # So you can use the API on your own localhost
                        response.addHeader("Sec-WebSocket-Accept", base64.b64encode(sha1.digest()).decode('ascii'))
                        response.create()
                        # self.print(response.responseBytes)
                        conn.send(response.responseBytes)
                        # self.print("Sent response!")
                    elif path == "/":
                        response = self.__serveFile("frontend/index.html")
                        conn.send(response.create())
                        self.exit()
                        return
                    elif path == "/index.css":
                        response = self.__serveFile("frontend/index.css")
                        conn.send(response.create())
                        self.exit()
                        return
                    elif path == "/index.js":
                        response = self.__serveFile("frontend/index.js")
                        conn.send(response.create())
                        self.exit()
                        return
                    elif path == "/favicon.ico":
                        response = self.__serveFile("frontend/favicon.ico")
                        conn.send(response.create())
                        self.exit()
                        return
                    else:
                        self.exit()
                        return
                else:
                    if path == "/api":
                        intData = list(data)
                        frames = []
                        while len(intData) > 2:
                            firstByte = intData.pop(0)
                            fin = (firstByte & 0x80) == 0x80
                            rsv = self.__bit(firstByte, 0x40)
                            rsv <<= 1
                            rsv += self.__bit(firstByte, 0x20)
                            rsv <<= 1
                            rsv += self.__bit(firstByte, 0x10)
                            opcode = self.__bit(firstByte, 0x08)
                            opcode <<= 1
                            opcode += self.__bit(firstByte, 0x04)
                            opcode <<= 1
                            opcode += self.__bit(firstByte, 0x02)
                            opcode <<= 1
                            opcode += self.__bit(firstByte, 0x01)
                            length = intData.pop(0)
                            mask = bool(self.__bit(length, 0x80))
                            if mask:
                                length -= 0x80
                            if length > 125:
                                if length == 126:
                                    size = 2
                                elif length == 127:
                                    size = 8
                                else:
                                    raise RuntimeError("Something went very wrong.")
                                length = 0
                                for _ in range(size):
                                    length <<= 8
                                    length += intData.pop(0)
                            maskingKeys = []
                            if mask:
                                for _ in range(4):
                                    maskingKeys.append(intData.pop(0))
                            rawFrameDataInts = []
                            for intI in range(length):
                                maskingKey = maskingKeys[intI % 4]
                                rawFrameDataInts.append(intData.pop(0) ^ maskingKey)
                            rawFrameData = bytes(rawFrameDataInts)
                            frames.append(WebSocketFrame(fin, rsv, opcode, payloadData=rawFrameData))
                            # self.print(f"({id}) Got frame (mask: {maskingKeys}, len: {length}):", rawFrameData)
                            if fin:  # If final frame, handle message
                                self.__handleAPIMessage(id, frames, conn)
                                frames = []
                i += 1
        except OSError:
            self.exit()
        self.print(f"({id}) Connection closed. Received:", allData)
        if self.captures:
            with open(f"captures/{id}.bin", "wb+") as f:
                f.write(allData)
                f.close()

    def __requestProcessor(self):
        while self.__alive:
            for request in self.__requests:
                if not request['closed']:
                    self.print(request)
                    if request['type'] == "websocket":
                        message = bytes([]).join(list(map(lambda sock: sock.create(), request['webSockets'])))
                        try:
                            self.conn.send(message)
                            request['closed'] = True
                        except OSError:
                            pass
                else:
                    self.__requests.remove(request)

    def onFrontendMessage(self, message: dict):
        self.__sendWebSocketJSON({
            'type': "frontendMessage",
            'frontendMessage': message
        })

    def onDownloaderTerminate(self):
        if self.isApiHandler():
            self.__sendWebSocketJSON({
                'type': "download",
                'download': "stop"
            })
        self.exit()

    def exit(self):
        self.conn.close()
        self.__alive = False

    def isAlive(self):
        return self.__alive

    def isApiHandler(self):
        return self.__apiHandler


class Server:
    def __init__(self, host="127.0.0.1", port=80, captures=False, debug_print=False):
        self.host = host
        self.port = port
        self.captures = captures
        self.debug_print = debug_print

        self.__connections = []
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind((self.host, self.port))
        self.__socket.listen()
        self.__connectionThread = Thread(target=self.__connectionProcessor)
        self.__connectionThread.start()

    def __connectionProcessor(self):
        while True:
            self.__connections = list(filter(lambda connection: connection.isAlive(), self.__connections))
            conn, addr = self.__socket.accept()
            # if self.debug_print:
            #     print(f"{addr[0]}:{addr[1]} has connected.")
            t = Thread(target=self.__handleConnection, args=(conn, addr))
            t.start()

    def __handleConnection(self, conn, addr):
        # if self.debug_print:
        #     print(conn, addr)
        # https://en.wikipedia.org/wiki/WebSocket
        # https://www.rfc-editor.org/rfc/rfc6455
        id = uuid.uuid4()
        connection = ServerConnection(conn, addr, id, self, self.captures, self.debug_print)
        self.__connections.append(connection)


if __name__ == '__main__':
    # frame = WebSocketFrame(payloadData=bytes(map(lambda a: 128, list(range(70000)))))
    frame = WebSocketFrame(payloadData=bytes("Hello", 'ascii'), hasMask=True,
                           maskingKey=bytes([0x37, 0xfa, 0x21, 0x3d]), opcode=0x1, fin=True)
    print(" ".join(list(map(lambda bit: hex(bit), frame.create()))))
