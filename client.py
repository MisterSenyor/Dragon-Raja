import socket
from settings import *


def main():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address, data = join(my_socket)
    print(data)


def join(server: socket):
    # Function that handles the client joining the server through the load balancer. Recives socket, returns server address ("IP",PORT) of server and data.
    server.sendto(build_header().zfill(HEADER_SIZE).encode(), (IP, PORT))
    data, server_address = server.recvfrom(HEADER_SIZE)
    data.decode()
    return server_address, data


def build_header():
    return 'hello  world'


if __name__ == '__main__':
    main()
