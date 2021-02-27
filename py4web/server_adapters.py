import logging
from .ombott.server_adapters import ServerAdapter

__all__ = ['geventWebSocketServer', 'wsgirefThreadingServer', 'rocketServer']

def geventWebSocketServer():
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    from geventwebsocket.logging import create_logger

    class GeventWebSocketServer(ServerAdapter):
        def run(self, handler):
            server = pywsgi.WSGIServer((self.host, self.port), handler, handler_class=WebSocketHandler, **self.options)

            if not self.quiet:
                server.logger = create_logger('geventwebsocket.logging')
                server.logger.setLevel(logging.INFO)
                server.logger.addHandler(logging.StreamHandler())

            server.serve_forever()
    return GeventWebSocketServer


def wsgirefThreadingServer():
    #https://www.electricmonk.nl/log/2016/02/15/multithreaded-dev-web-server-for-the-python-bottle-web-framework/

    from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, ServerHandler

    from wsgiref.simple_server import make_server
    from socketserver import ThreadingMixIn
    import socket
    from concurrent.futures import ThreadPoolExecutor  # pip install futures

    class WSGIRefThreadingServer(ServerAdapter):
        def run(self, app):

            class PoolMixIn(ThreadingMixIn):
                def process_request(self, request, client_address):
                    return self.pool.submit(self.process_request_thread, request, client_address)

            #class ThreadingWSGIServer(PoolMixIn, WSGIServer):
            class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
                daemon_threads = True
                pool = ThreadPoolExecutor(max_workers=40)

            class Server:
                def __init__(self, host = '127.0.0.1', port= 8000, app = None, handler_cls = None):
                    self.listen, self.port = host, port
                    self.wsgi_app = app
                    self.handler_cls = handler_cls

                def set_app(self, app):
                    self.wsgi_app = app
                def get_app(self):
                    return self.wsgi_app
                def serve_forever(self):
                    self.server = make_server(
                        self.listen, self.port, self.wsgi_app, ThreadingWSGIServer, self.handler_cls
                    )
                    self.server.serve_forever()

            class FixedHandler(WSGIRequestHandler):
                def handle(self):
                    """Handle a single HTTP request"""

                    self.raw_requestline = self.rfile.readline(65537)
                    if len(self.raw_requestline) > 65536:
                        self.requestline = ''
                        self.request_version = ''
                        self.command = ''
                        self.send_error(414)
                        return

                    if not self.parse_request(): # An error code has been sent, just exit
                        return

                    handler = ServerHandler(
                        self.rfile, self.wfile, self.get_stderr(), self.get_environ(),
                        multithread=True,
                    )
                    handler.request_handler = self      # backpointer for logging
                    handler.run(self.server.get_app())

                def address_string(self): # Prevent reverse DNS lookups please.
                    return self.client_address[0]
                def log_request(*args, **kw):
                    if not self.quiet:
                        return WSGIRequestHandler.log_request(*args, **kw)

            handler_cls = self.options.get('handler_class', FixedHandler)
            server_cls  = Server

            if ':' in self.host: # Fix wsgiref for IPv6 addresses.
                if getattr(server_cls, 'address_family') == socket.AF_INET:
                    class server_cls(server_cls):
                        address_family = socket.AF_INET6

            #srv = make_server(self.host, self.port, app, server_cls, handler_cls)
            srv = server_cls(self.host, self.port, app, handler_cls)
            srv.serve_forever()
    return WSGIRefThreadingServer

def rocketServer():
    from . rocket import Rocket
    import logging
    import logging.handlers
    import sys

    class RocketServer(ServerAdapter):
        def run(self, app):
            if not self.quiet:
                log = logging.getLogger('Rocket')
                log.setLevel(logging.INFO)
                log.addHandler(logging.StreamHandler(sys.stdout))
            server = Rocket((self.host, self.port), 'wsgi', dict(wsgi_app = app))
            server.start()

    return RocketServer
