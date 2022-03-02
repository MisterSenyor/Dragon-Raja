import socket
import threading
from settings import *


def handle_player(conn: socket.socket, seed: int):
    print("HELLO")


def build_header():
    return 'Hello client'


def main():
    connections = {}

    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((IP, PORT))
    while True:
        data, client_address = server.recvfrom(HEADER_SIZE)
        data = data.decode()
        print(data)

        server.sendto(build_header().zfill(HEADER_SIZE).encode(), client_address)
        # conduct handshake
        # thread = threading.Thread(target=handle_player, args=[conn, 1337])
        # thread.start()


if __name__ == '__main__':
    main()