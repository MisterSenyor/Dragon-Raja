import socket
from settings import *

def main():
    load_balancer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def join(server: socket):
    # Function that handles the client joining the server through the load balancer. Recives socket, returns port and ip of segment server.
    server.sendto(build_header.encode(), (IP, PORT))
    port, addr = server.recvfrom((IP, PORT))
    return 'hello  world'

def build_header():
    return 'hello  world'.zfill(HEADER_SIZE)

if __name__ == '__main__':
    main()