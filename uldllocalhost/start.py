#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from uldllocalhost import Server
import uldlib.cmd

print("Starting...")
server = Server(port=666, captures=False, debug_print=False)
print(f"Started server at http://{server.host}:{server.port}")
