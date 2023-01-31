#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import base64
import hashlib
import socket
import uuid
from threading import Thread


class Server:
    def __init__(self, host="127.0.0.1", port=80):
        self.host = host
        self.port = port

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
        id = uuid.uuid4()
        allData = b''
        message = b''
        messages = []
        while True:
            data = conn.recv(4096)
            if not data:
                break
            allData += data
            print(data)
            intData = list(data)
            """while len(intData) > 2:
                firstByte = intData.pop(0)
                fin = firstByte & 0x80
                rsv = firstByte & 0x40
                rsv <<= firstByte & 0x20
                rsv <<= firstByte & 0x10
                opcode = firstByte & 0x08
                opcode <<= firstByte & 0x04
                opcode <<= firstByte & 0x02
                opcode <<= firstByte & 0x01
                length = intData.pop(0)
                mask = length & 0x80 > 1
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
                maskingKey = 0
                if mask:
                    for _ in range(4):
                        maskingKey <<= 8
                        mask += intData.pop(0)
                print(f"({id}) Got frame (mask: {maskingKey}, len: {length}):", bytes(intData[:length]))"""
            if not data.decode('ascii').startswith("GET /hahaha"):
                conn.close()
                return
            sha1 = hashlib.sha1()
            sha1.update(base64.b64decode(input("Tell us the base64: ")))
            sha1.update(bytes("258EAFA5-E914-47DA-95CA-C5AB0DC85B11", 'ascii'))
            print("Hashed:", sha1.digest(), f"===> {base64.b64encode(sha1.digest()).decode('ascii')}")
            conn.send(bytes(
                f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {base64.b64encode(sha1.digest()).decode('ascii')}\r\nSec-WebSocket-Protocol: chat\r\n\r\n",
                'utf-8'))
            print("Sent response!")
        print(f"({id}) Connection closed. Received:", allData)
        with open(f"captures/{id}.bin", "wb+") as f:
            f.write(allData)
            f.close()
