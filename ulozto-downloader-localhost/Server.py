#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import socket
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
        allData = b''
        while True:
            data = conn.recv(4096)
            if not data or data == b'':
                break
            allData += data
            print(data)
            conn.send(bytes(
                "HTTP/1.1 101 Switching Protocols\nUpgrade: websocket\nConnection: Upgrade\nSec-WebSocket-Accept: HSmrc0sMlYUkAGmm5OPpG2HaGWk=\nSec-WebSocket-Protocol: chat",
                'utf-8'))
        print("Ahhhhhhhhhh")
        print("Received:", allData)
