import socket


class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.IP = socket.gethostbyname(socket.gethostname())
        self.port = 1337
        self.HEADER_SIZE = 32
        self.ENCODING = 'utf-8'
        self.addr = (self.IP, self.port)
        self.pos = ((1400, 1360))


    def getPos(self):
        return self.pos

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
    print(n.send((1399, 1360)))
    print(n.send((1398, 1360)))
    print(n.send((1397, 1360)))
    print(n.send((1396, 1360)))
    print(n.send((1395, 1360)))
    print(n2.send((2001, 1360)))



if __name__ == '__main__':
    main()
