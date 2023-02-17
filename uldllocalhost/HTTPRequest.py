#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from HTTPHeader import HTTPHeader


class HTTPRequest:
    CRLF = bytes("\r\n", "ascii")
    SP = bytes(" ", "ascii")

    HEADER_SEP = bytes(": ", "ascii")

    def __init__(self, requestBytes=bytes([])):
        self.requestBytes = requestBytes

        self.method = None
        self.requestURI = None
        self.HTTPVersion = None
        self.headers = []
        self.body = None

        if len(requestBytes):
            self.__parse()

    def __parse(self):
        lines = self.requestBytes.split(HTTPRequest.CRLF)
        requestLine = lines.pop(0)
        self.method, self.requestURI, self.HTTPVersion = requestLine.split(HTTPRequest.SP)
        while len(lines) and len(lines[0]) != 0:
            headerLine = lines.pop(0)
            name, value = headerLine.split(HTTPRequest.HEADER_SEP)
            self.headers.append(HTTPHeader(name, value))
        self.body = HTTPRequest.CRLF.join(lines)

    def getHeaders(self, name):
        return list(filter(lambda header: header.getName() == name, self.headers))

    def getRawHeader(self, name, index=0):
        headers = self.getHeaders(name)
        if len(headers) <= index:
            return None
        return headers[index]

    def getHeader(self, name, index=0):
        header = self.getRawHeader(name,index)
        if not header:
            return None
        return header.getValue()
