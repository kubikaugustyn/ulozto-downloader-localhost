#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import importlib.util
import signal
import os
import sys
from os import path
from uldlib import downloader, captcha, __path__, const
from uldlib import utils
from uldlib.torrunner import TorRunner
from uldlib.utils import LogLevel
from uldllocalhost.Settings import Settings
from uldllocalhost.WebFrontend import WebFrontend


class DownloaderState:
    WAITING = "waiting"
    RUNNING = "running"
    STOPPED = "stopped"
    DONE = "done"


# Just edited uldllib.cmd
class Downloader:
    def __init__(self, serverConnection):
        self.exitHandler = None
        self.serverConnection = serverConnection
        self.__state = DownloaderState.WAITING

    def run(self, args: Settings):
        if not self.serverConnection or not self.serverConnection.isAlive():
            raise ValueError("Can't run downloader with no API connection")
        self.__state = DownloaderState.RUNNING
        # TODOne: implemented other frontend ;-)
        frontend = WebFrontend(self.serverConnection, show_parts=args.parts_progress, logfile=args.log)

        tfull_available = importlib.util.find_spec('tensorflow') and importlib.util.find_spec('tensorflow.lite')
        tflite_available = importlib.util.find_spec('tflite_runtime')
        tkinter_available = importlib.util.find_spec('tkinter')

        # Autodetection
        if not args.auto_captcha and not args.manual_captcha:
            if tfull_available:
                frontend.main_log("[Autodetect] tensorflow.lite available, using --auto-captcha")
                args.auto_captcha = True
            elif tflite_available:
                frontend.main_log("[Autodetect] tflite_runtime available, using --auto-captcha")
                args.auto_captcha = True
            elif tkinter_available:
                frontend.main_log("[Autodetect] tkinter available, using --manual-captcha")
                args.manual_captcha = True
            else:
                frontend.main_log(
                    "[Autodetect] WARNING: No tensorflow.lite or tflite_runtime and no tkinter available, cannot solve CAPTCHA (only direct download available)",
                    level=LogLevel.WARNING
                )

        if args.auto_captcha:
            if not (tfull_available or tflite_available):
                frontend.main_log(
                    'ERROR: --auto-captcha used but neither tensorflow.lite nor tflite_runtime are available',
                    level=LogLevel.ERROR)
                sys.exit(1)

            model_path = path.join(__path__[0], const.MODEL_FILENAME)
            solver = captcha.AutoReadCaptcha(model_path, const.MODEL_DOWNLOAD_URL, frontend)
        elif args.manual_captcha:
            if not tkinter_available:
                frontend.main_log('ERROR: --manual-captcha used but tkinter not available', level=LogLevel.ERROR)
                sys.exit(1)

            solver = captcha.ManualInput(frontend)
        else:
            solver = captcha.Dummy(frontend)

        # enables ansi escape characters in terminal on Windows
        if os.name == 'nt':
            os.system("")

        tor = TorRunner(args.temp, frontend.tor_log)
        d = downloader.Downloader(tor, frontend, solver)

        # Register sigint handler
        def sigint_handler():
            if d.terminating:
                return  # Already terminating
            d.terminate()
            tor.stop()
            print('Program terminated.')
            self.__state = DownloaderState.STOPPED
            self.serverConnection.onDownloaderTerminate()
            sys.exit(1)

        # signal.signal(signal.SIGINT, sigint_handler) # Ctrl + C
        self.exitHandler = sigint_handler

        try:
            for url in args.urls:
                d.download(url, args.parts, args.output, args.temp, args.yes, args.conn_timeout)
                # do clean only on successful download (no exception)
                d.clean()
        except utils.DownloaderStopped:
            pass
        except utils.DownloaderError as e:
            frontend.main_log(str(e), level=LogLevel.ERROR)
        finally:
            d.terminate()
            tor.stop()

        self.__state = DownloaderState.DONE

    def getState(self):
        return self.__state
