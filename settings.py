import socket

IP = socket.gethostbyname(socket.gethostname())
PORT = 1337
HEADER_SIZE = 32
ENCODING = 'utf-8'
TEXT = "hello there"