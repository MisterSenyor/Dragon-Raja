import socket
from settings import *

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.sendto('hello there'.encode().zfill(HEADER_SIZE), (IP, PORT))

if __name__ == '__main__':
    main()