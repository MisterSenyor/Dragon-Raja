import socket
from settings import *

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.sendto('124'.encode().zfill(HEADER_SIZE), (IP, PORT))

if __name__ == '__main__':
    main()