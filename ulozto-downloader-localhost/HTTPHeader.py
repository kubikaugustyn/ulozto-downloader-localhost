#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

class HTTPHeader:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def getName(self):
        return self.name

    def getValue(self):
        return self.value
