import json
import socket
from settings import *


class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.IP = SERVER_IP
        self.port = SERVER_PORT
        self.HEADER_SIZE = HEADER_SIZE
        self.ENCODING = ENCODING
        self.addr = (self.IP, self.port)
        self.pos = ((1400, 1360))
        self.id = self.connect()

    def serialize_cmd(seld, data):
        data = json.dumps(data)
        return data

    def connect(self):
        data = {"cmd": "connect", "id": 0}
        data = self.serialize_cmd(data)
        id = self.send(data)
        return id
    def send(self, data):
        try:
            self.client.sendto(str.encode(data), self.addr)
            (data, addr) = self.client.recvfrom(self.HEADER_SIZE)
            return data.decode()
        except socket.error as e:
            print(e)



def main():
    n2 = Network()
    n = Network()
    print(n2.id)
    print(n.id)
    n.send(n.serialize_cmd({"cmd": "attack", "id": n.id}))



if __name__ == '__main__':
    main()
