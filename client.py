import socket
from settings import *

def main():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_port , server_ip = join(my_socket)

def join(server: socket):
    # Function that handles the client joining the server through the load balancer. Recives socket, returns port and ip of segment server.
    server.sendto(build_header.encode(), (IP, PORT))
    data , load_balancer_ip = server.recvfrom((IP, PORT))
    data.decode()
    return 'hello  world'

def build_header():
    return 'hello  world'.zfill(HEADER_SIZE)

if __name__ == '__main__':
    main()