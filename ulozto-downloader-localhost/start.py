#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from Server import Server
import uldlib.cmd

print("Starting...")
server = Server(port=666)
print(f"Started server at http://{server.host}:{server.port}")
