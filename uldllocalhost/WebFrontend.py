#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from uldlib.frontend import *

from .Server import *


# Custom frontend
class WebFrontend(Frontend):
    cli_initialized: bool
    show_parts: bool
    logfile: Optional[TextIOWrapper] = None

    last_log: Tuple[str, LogLevel]

    last_captcha_log: Tuple[str, LogLevel]
    last_captcha_stats: Dict[str, int]

    prompts: Dict[str, str | None]

    serverConnection: ServerConnection

    def __init__(self, serverConnection, show_parts: bool = False, logfile: str = ""):
        self.serverConnection = serverConnection
        super().__init__(supports_prompt=True)
        self.cli_initialized = False
        self.last_log = ("", LogLevel.INFO)
        self.last_captcha_log = ("", LogLevel.INFO)
        self.last_captcha_stats = None
        self.show_parts = show_parts
        self.prompts = {}
        if logfile:
            self.logfile = open(logfile, 'a')

    def __del__(self):
        if self.logfile:
            self.logfile.close()

    def _log_print(self, msg: str, progress: bool):
        if progress:
            # sys.stdout.write(msg + "\033[K\r")
            self.serverConnection.onFrontendMessage({
                'type': "write",
                'write': msg + "\033[K\r"
            })
        else:
            # print(msg)
            self.serverConnection.onFrontendMessage({
                'type': "print",
                'print': msg
            })

    def _log_logfile(self, prefix: str, msg: str, progress: bool, level: LogLevel):
        if progress or self.logfile is None:
            return

        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logfile.write(f"{t} {prefix}\t[{level.name}] {msg}\n")
        self.logfile.flush()

    def tor_log(self, msg: str, level: LogLevel = LogLevel.INFO, progress: bool = False):
        self.last_captcha_log = (msg, level)  # shares same log with CAPTCHA
        self._log_logfile('TOR ', msg, progress=progress, level=level)
        if not self.cli_initialized:
            self._log_print(colors.blue("[TOR]\t") + utils.color(msg, level), progress=progress)

    def captcha_log(self, msg: str, level: LogLevel = LogLevel.INFO, progress: bool = False):
        self.last_captcha_log = (msg, level)
        self._log_logfile('CAPTCHA', msg, progress=progress, level=level)
        if not self.cli_initialized:
            self._log_print(colors.blue("[Link solve]\t") + utils.color(msg, level), progress=progress)

    def main_log(self, msg: str, level: LogLevel = LogLevel.INFO, progress: bool = False):
        self.last_log = (msg, level)
        self._log_logfile('MAIN', msg, progress=progress, level=level)
        if not self.cli_initialized:
            self._log_print(utils.color(msg, level), progress=progress)

    def captcha_stats(self, stats: Dict[str, int]):
        self.last_captcha_stats = stats

    def promptCaptcha(self, imageB64: str, stop_event: threading.Event = None) -> str:
        id = uuid.uuid4().hex
        self.prompts[id] = None
        self.serverConnection.onFrontendMessage({
            'type': "prompt",
            'id': id,
            'promptCaptcha': imageB64
        })
        while self.prompts[id] is None:
            # Wait for response from the user
            if stop_event and stop_event.is_set():
                break
        return self.prompts[id].strip()

    def prompt(self, msg: str, level: LogLevel = LogLevel.INFO) -> str:
        # print(utils.color(msg, level))
        id = uuid.uuid4().hex
        self.prompts[id] = None
        self.serverConnection.onFrontendMessage({
            'type': "prompt",
            'id': id,
            'prompt': msg,
            'level': level.name
        })
        while self.prompts[id] is None:
            pass  # Wait for response from the user
        # print("Answer:", self.prompts[id])
        return self.prompts[id].strip()

    @staticmethod
    def _stat_fmt(stats: Dict[str, int]):
        count = colors.blue(stats['all'])
        ok = colors.green(stats['ok'])
        bad = colors.red(stats['bad'])
        lim = colors.red(stats['lim'])
        blo = colors.red(stats['block'])
        net = colors.red(stats['net'])
        return f"[Ok: {ok} / {count}] :( [Badcp: {bad} Limited: {lim} Censored: {blo} NetErr: {net}]"

    def _print(self, text, x=0, y=0):
        # sys.stdout.write("\033[{};{}H".format(y, x))
        self.serverConnection.onFrontendMessage({
            'type': "write",
            'write': "\033[{};{}H".format(y, x)
        })
        # sys.stdout.write("\033[K")
        self.serverConnection.onFrontendMessage({
            'type': "write",
            'write': "\033[K"
        })
        # sys.stdout.write(text)
        self.serverConnection.onFrontendMessage({
            'type': "write",
            'write': text
        })
        # sys.stdout.flush()
        self.serverConnection.onFrontendMessage({
            'type': "flush"
        })

    def run(self, info: DownloadInfo, parts: List[DownloadPart], stop_event: threading.Event, terminate_func):
        try:
            self._loop(info, parts, stop_event)
        except Exception:
            if self.cli_initialized:
                y = info.parts + CLI_STATUS_STARTLINE + 4
                sys.stdout.write("\033[{};{}H".format(y, 0))
                sys.stdout.write("\033[?25h")  # show cursor
                self.cli_initialized = False
                print("")
            print_exc()
            terminate_func()

    def _loop(self, info: DownloadInfo, parts: List[DownloadPart], stop_event: threading.Event):
        os.system('cls' if os.name == 'nt' else 'clear')
        sys.stdout.write("\033[?25l")  # hide cursor
        self.cli_initialized = True

        print(colors.blue("File:\t\t") + colors.bold(info.filename))
        print(colors.blue("URL:\t\t") + info.url)
        print(colors.blue("Download type:\t") + info.download_type)
        print(colors.blue("Size / parts: \t") +
              colors.bold(f"{round(info.total_size / 1024 ** 2, 2)}MB => " +
                          f"{info.parts} x {round(info.part_size / 1024 ** 2, 2)}MB"))

        t_start = time.time()
        s_start = 0
        for part in parts:
            (_, _, size) = part.get_frontend_status()
            s_start += size
        last_bps = [(s_start, t_start)]

        y = 0

        while True:
            t = time.time()
            # Get parts info
            lines = []
            s = 0
            for part in parts:
                (line, level, size) = part.get_frontend_status()
                lines.append(utils.color(line, level))
                s += size

            y = CLI_STATUS_STARTLINE

            # Print CAPTCHA/TOR status
            (msg, level) = self.last_captcha_log
            self._print(
                colors.yellow("[Link solve]\t") +
                utils.color(msg, level),
                y=y
            )
            y += 1
            if self.last_captcha_stats is not None:
                self._print(
                    colors.yellow("\t\t") + self._stat_fmt(self.last_captcha_stats),
                    y=y
                )
                y += 1

            # Print overall progress line
            if t == t_start:
                total_bps = 0
                now_bps = 0
            else:
                total_bps = (s - s_start) / (t - t_start)
                # Average now bps for last 10 measurements
                if len(last_bps) >= 10:
                    last_bps = last_bps[1:]
                (s_last, t_last) = last_bps[0]
                now_bps = (s - s_last) / (t - t_last)
                last_bps.append((s, t))

            remaining = (info.total_size - s) / total_bps if total_bps > 0 else 0

            self._print(colors.yellow(
                f"[Progress]\t"
                f"{(s / 1024 ** 2):.2f} MB"
                f" ({(s / info.total_size * 100):.2f} %)"
                f"\tavg. speed: {(total_bps / 1024 ** 2):.2f} MB/s"
                f"\tcurr. speed: {(now_bps / 1024 ** 2):.2f} MB/s"
                f"\tremaining: {timedelta(seconds=round(remaining))}"),
                y=y
            )
            y += 1

            # Print last log message
            (msg, level) = self.last_log
            self._print(
                colors.yellow("[STATUS]\t") +
                (msg if level == LogLevel.INFO else colors.negative(utils.color(msg, level))),
                y=y
            )
            y += 1

            # Print parts
            if self.show_parts:
                for (line, part) in zip(lines, parts):
                    self._print(
                        colors.blue(f"[Part {part.id}]") + f"\t{line}",
                        y=(y + part.id))

            if stop_event.is_set():
                break

            time.sleep(0.5)

        if self.cli_initialized:
            y = info.parts + CLI_STATUS_STARTLINE + 4
            sys.stdout.write("\033[{};{}H".format(y + 2, 0))
            sys.stdout.write("\033[?25h")  # show cursor
            self.cli_initialized = False

        elapsed = time.time() - t_start
        # speed in bytes per second:
        speed = (s - s_start) / elapsed if elapsed > 0 else 0
        print(colors.blue("Statistics:\t") + "Downloaded {}{} MB in {} (average speed {} MB/s)".format(
            round((s - s_start) / 1024 ** 2, 2),
            "" if s_start == 0 else (
                    "/" + str(round(info.total_size / 1024 ** 2, 2))
            ),
            str(timedelta(seconds=round(elapsed))),
            round(speed / 1024 ** 2, 2)
        ))
