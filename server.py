import socket
import threading
from settings import *

connections = {}

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((IP, PORT))

def handle_player(conn: socket.socket, seed: int):
    

def main():
    data, conn = server.recvfrom(HEADER_SIZE)
    data = data.decode(ENCODING)
    # conduct handshake
    thread = threading.Thread(target=handle_player, args=[conn, 1337])
    
if __name__ == '__main__':
    main()
