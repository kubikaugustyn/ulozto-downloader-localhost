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
    def __init__(self, fin, rsv, opcode, payloadData):
        self.fin = fin
        self.rsv = rsv
        self.opcode = opcode
        self.payloadData = payloadData

    def __str__(self):
        return f"<Frame: {self.opcode} containing {self.payloadData}>"


class Server:
    def __init__(self, host="127.0.0.1", port=80):
        self.host = host
        self.port = port

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind((self.host, self.port))
        self.__socket.listen()
        self.__connectionThread = Thread(target=self.__connectionProcessor)
        self.__connectionThread.start()

    # byte & numb is 1
    # 0110 & 100 is 1
    # 0110 & 1000 is 0
    def __bit(self, byte, numb):
        return int((byte & numb) == numb)

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
        allData = b''
        message = b''
        messages = []
        i = 0
        request = None
        path = None
        while True:
            data = conn.recv(1024 * 8)
            if not data:
                break
            allData += data
            # print(data)
            if i == 0:  # Don't exit on second request
                request = HTTPRequest(data)
                requestURI = request.requestURI.decode('ascii')
                if request.getHeader(bytes("Host", 'ascii')) is None:
                    if self.host == "127.0.0.1" and requestURI.startswith(f"localhost:{self.port}"):
                        path = requestURI[len(f"localhost:{self.port}"):]
                    elif requestURI.startswith(f"{self.host}:{self.port}"):
                        path = requestURI[len(f"{self.host}:{self.port}"):]
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
                    return
                elif path == "/index.css":
                    response = self.__serveFile("frontend/index.css")
                    conn.send(response.create())
                    return
                elif path == "/index.js":
                    response = self.__serveFile("frontend/index.js")
                    conn.send(response.create())
                    return
                elif path == "/favicon.ico":
                    response = self.__serveFile("frontend/favicon.ico")
                    conn.send(response.create())
                    return
                else:
                    conn.close()
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
                        frames.append(WebSocketFrame(fin, rsv, opcode, rawFrameData))
                        print(f"({id}) Got frame (mask: {maskingKeys}, len: {length}):", rawFrameData)
                        if fin:  # If final frame, handle message
                            self.__handleAPIMessage(id, frames, conn)
                            frames = []
            i += 1
        print(f"({id}) Connection closed. Received:", allData)
        with open(f"captures/{id}.bin", "wb+") as f:
            f.write(allData)
            f.close()

    def __serveFile(self, fileName):
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
