import socket
import threading
from settings import *

connections = {}

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((IP, PORT))

def handle_player(conn: socket.socket, seed: int):
    print("HELLO")

def main():
    while True:
        data, conn = server.recvfrom(HEADER_SIZE)
        data = data.decode(ENCODING)
        print(data)
        # conduct handshake
        thread = threading.Thread(target=handle_player, args=[conn, 1337])
        thread.start()
    
if __name__ == '__main__':
    main()
