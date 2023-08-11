#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import base64
import threading

import requests
from uldlib.captcha import CaptchaSolver
from PIL import Image
from io import BytesIO

from uldllocalhost.WebFrontend import WebFrontend


class ManualWebInput(CaptchaSolver):
    """Display captcha from given URL and ask user for input in GUI window."""
    frontend: WebFrontend

    def __init__(self, frontend):
        super().__init__(frontend)

    def solve(self, img_url: str, stop_event: threading.Event = None) -> str:
        u = requests.get(img_url)
        raw_data = u.content
        b64 = base64.b64encode(raw_data)
        return self.frontend.promptCaptcha(b64.decode('ascii'), stop_event)
