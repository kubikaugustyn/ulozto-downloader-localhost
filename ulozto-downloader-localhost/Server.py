#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import base64
import hashlib
import socket
import uuid
from threading import Thread
from HTTPRequest import *
from HTTPResponse import *


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
        lengthBytes = list(map(lambda hexStr: int(hexStr, 16), self.__groupString(hex(length)[2:], 2)))
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
    def __init__(self, conn, addr, id, server):
        self.conn = conn
        self.addr = addr
        self.id = id
        self.server = server

        self.__alive = True
        self.__responseThread = Thread(target=self.__responseProcessor)  # Receive data from client, always runs
        self.__requestThread = Thread(
            target=self.__requestProcessor)  # Send data to client, start only if we have request
        self.__requests = []

        self.__responseThread.start()

    # byte & numb is 1
    # 0110 & 100 is 1
    # 0110 & 1000 is 0
    def __bit(self, byte, numb):
        return int((byte & numb) == numb)

    def __serveFile(self, fileName):
        print(f"Serving file: {fileName}")
        response = HTTPResponse()
        response.setStatusCode(200).setReasonPhrase("OK")
        with open(fileName, "rb+") as f:
            response.setBody(f.read())
        return response

    def __handleAPIMessage(self, id, messageFrames, connection):
        # print(f"({id}) Received message: {list(map(lambda frame: str(frame), messageFrames))}")
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
        payload = bytes([]).join(payloads)
        if opcode == 0x1:  # Denotes a text frame
            payload = payload.decode('utf-8')
            print(f"We received message: {payload}")
        elif opcode == 0x2:  # Denotes a binary frame
            print(f"We received binary: {payload}")
        elif opcode == 0x8:  # Denotes a connection close
            connection.close()
        elif opcode == 0x9:  # Denotes a ping
            print("We were pinged!")
        elif opcode == 0xA:  # Denotes a pong
            print("We received pong!")
        else:
            raise RuntimeError("Wtf?!")

    def __addRequest(self, type, data):
        request = {
            'type': type,
            'response': None
        }
        for key in data:
            request[key] = data[key]
        self.__requests.append(request)
        if not self.__requestThread.isAlive():
            self.__requestThread.start()

    def __addWebSocketRequest(self, webSocket):
        self.__addRequest("websocket", {'webSocket': webSocket})

    def __responseProcessor(self):
        conn = self.conn

        allData = b''
        i = 0
        path = None
        while self.__alive:
            data = conn.recv(1024 * 8)
            if not data:
                break
            allData += data
            # print(data)
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
                    sha1 = hashlib.sha1()
                    hashedText = request.getHeader(bytes("Sec-WebSocket-Key", 'ascii')).decode(
                        'ascii') + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                    sha1.update(bytes(hashedText, 'ascii'))
                    # print("Hashed:", sha1.digest(), f"===> {base64.b64encode(sha1.digest()).decode('ascii')}")
                    # f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {base64.b64encode(sha1.digest()).decode('ascii')}\r\n\r\n",
                    response = HTTPResponse()
                    response.setStatusCode(101).setReasonPhrase("Switching Protocols")
                    response.addHeader("Upgrade", "websocket").addHeader("Connection", "Upgrade")
                    response.addHeader("Access-Control-Allow-Origin",
                                       "*")  # So you can use the API on your own localhost
                    response.addHeader("Sec-WebSocket-Accept", base64.b64encode(sha1.digest()).decode('ascii'))
                    response.create()
                    # print(response.responseBytes)
                    conn.send(response.responseBytes)
                    # print("Sent response!")
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
                        print(f"({id}) Got frame (mask: {maskingKeys}, len: {length}):", rawFrameData)
                        if fin:  # If final frame, handle message
                            self.__handleAPIMessage(id, frames, conn)
                            frames = []
            i += 1
        print(f"({id}) Connection closed. Received:", allData)
        with open(f"captures/{id}.bin", "wb+") as f:
            f.write(allData)
            f.close()

    def __requestProcessor(self):
        while self.__alive:
            pass

    def exit(self):
        self.conn.close()
        self.__alive = False


class Server:
    def __init__(self, host="127.0.0.1", port=80):
        self.host = host
        self.port = port

        self.__connections = []
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind((self.host, self.port))
        self.__socket.listen()
        self.__connectionThread = Thread(target=self.__connectionProcessor)
        self.__connectionThread.start()

    def __connectionProcessor(self):
        while True:
            conn, addr = self.__socket.accept()
            print(f"{addr[0]}:{addr[1]} has connected.")
            t = Thread(target=self.__handleConnection, args=(conn, addr))
            t.start()

    def __handleConnection(self, conn, addr):
        # print(conn, addr)
        # https://en.wikipedia.org/wiki/WebSocket
        # https://www.rfc-editor.org/rfc/rfc6455
        id = uuid.uuid4()
        connection = ServerConnection(conn, addr, id, self)
        self.__connections.append(connection)


if __name__ == '__main__':
    # frame = WebSocketFrame(payloadData=bytes(map(lambda a: 128, list(range(70000)))))
    frame = WebSocketFrame(payloadData=bytes("Hello", 'ascii'), hasMask=True,
                           maskingKey=bytes([0x37, 0xfa, 0x21, 0x3d]), opcode=0x1, fin=True)
    print(" ".join(list(map(lambda bit: hex(bit), frame.create()))))
