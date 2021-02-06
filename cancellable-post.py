import logging
import socket
import threading
import time
from functools import partial
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any, Callable, Dict, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, Request, build_opener

log = logging.getLogger(__name__)


class MyHTTPConnection(HTTPConnection):
    def connect(self) -> None:
        # Unlike HTTPConnection.connect, this creates the socket so that it is
        # assinged to self.sock before it's connected. That way it can be shut
        # down during the connecting.
        self.sock = socket.socket()
        self.sock.connect((self.host, self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


# HTTPSConnection does super().connect(), which calls MyHTTPConnection.connect,
# and then it SSL-wraps the socket created by MyHTTPConnection.
class MyHTTPSConnection(HTTPSConnection, MyHTTPConnection):
    def __init__(self, *args: Any, cancellable: 'CancellablePost', **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        cancellable.connection = self


class CancellablePost:

    def __init__(self) -> None:
        self.connection: Optional[MyHTTPConnection] = None
        self.result: Optional[str] = None
        self._canceled = False

    def run(self, url: str, params: Dict[str, str]) -> None:
        # kwargs of do_open() go to MyHTTPSConnection
        handler = HTTPSHandler()
        handler.https_open = partial(handler.do_open, MyHTTPSConnection, cancellable=self)

        try:
            with build_opener(handler).open(Request(url, data=urlencode(params).encode('utf-8'))) as response:
                self.result = response.read().decode()
        except (OSError, UnicodeError, URLError, HTTPException):
            if self._canceled:
                log.debug("Error when doing HTTP POST, likely due to canceling", exc_info=True)
            else:
                log.exception("Error when doing HTTP POST")

    def cancel(self) -> None:
        if self.connection is not None and not self._canceled:
            self._canceled = True
            print("Shutdown begins")
            self.connection.sock.shutdown(socket.SHUT_RDWR)
            print("Shutdown complete")


def call_soon(f: Callable[[], None]) -> None:
    time.sleep(0.5)
    f()


request = CancellablePost()
threading.Thread(target=call_soon, args=[request.cancel]).start()
request.run('https://httpbin.org/delay/3', {'syntax': 'python', 'content': 'print("hello")'})
#request.run('https://dpaste.com/api/v2/', {'syntax': 'python', 'content': 'print("hello")'})
print('Result =', request.result)
