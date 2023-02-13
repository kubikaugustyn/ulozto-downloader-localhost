#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from HTTPHeader import HTTPHeader


class HTTPResponse:
    CRLF = bytes("\r\n", "ascii")
    SP = bytes(" ", "ascii")

    BLANK = bytes([])
    HEADER_SEP = bytes(": ", "ascii")

    def __init__(self):
        self.responseBytes = None

        self.HTTPVersion = bytes("HTTP/1.1", 'ascii')
        self.statusCode = HTTPResponse.BLANK
        self.reasonPhrase = HTTPResponse.BLANK
        self.headers = []
        self.body = HTTPResponse.BLANK

    def addHeader(self, name, value):
        self.headers.append(HTTPHeader(bytes(name, 'ascii'), bytes(value, 'ascii')))

        return self

    def setHTTPVersion(self, version):
        self.HTTPVersion = bytes(version, 'ascii')

        return self

    def setStatusCode(self, statusCode=200):
        self.statusCode = bytes(str(statusCode), 'ascii')

        return self

    def setReasonPhrase(self, reasonPhrase):
        self.reasonPhrase = bytes(reasonPhrase, 'ascii')

        return self

    def setBody(self, body):
        self.body = body

        return self

    def create(self):
        requestLine = HTTPResponse.SP.join([self.HTTPVersion, self.statusCode, self.reasonPhrase])
        lines = [requestLine]
        for header in self.headers:
            lines.append(HTTPResponse.HEADER_SEP.join([header.getName(), header.getValue()]))
        lines.append(HTTPResponse.BLANK)  # To add the extra CRLF after headers
        lines.append(self.body)
        self.responseBytes = HTTPResponse.CRLF.join(lines)
        return self.responseBytes
