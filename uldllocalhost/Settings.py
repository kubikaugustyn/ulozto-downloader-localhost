#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from typing import List, Optional


class Settings:
    urls: List[str]
    parts: int
    output: str
    temp: str
    yes: bool
    parts_progress: bool
    log: Optional[str]
    auto_captcha: bool
    manual_captcha: bool
    conn_timeout: int
