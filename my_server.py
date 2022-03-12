import json
import time
import threading
import socket
import settings
import time


class server:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ip = socket.gethostbyname(socket.gethostname())
        print("Server ip: {}".format(self.ip))
        self.clients = []
        self.clientsAmount = 0
        self.address = (self.ip, settings.SERVER_PORT)

    def add(self, address):
        self.clients.append(address)
        data = json.dumps({'cmd': 'new', 'id': self.clientsAmount})
        self.clientsAmount += 1
        self.socket.sendto(data.encode(), address)

    def send_data(self, data):
        for i in self.clients:
            self.socket.sendto(data, i)

    def receive_packets(self, arr):
        while True:
            (msg, client_address) = self.socket.recvfrom(settings.HEADER_SIZE)
            print("received packet. address: {}".format(client_address))
            data = json.loads(msg.decode())
            print("data: {}".format(data))
            if client_address not in self.clients and "cmd" in data and data["cmd"] == "new":
                self.add(client_address)
            else:
                arr.append(data)
                print(arr)

    def handle_updates(self, arr):
        pass

    def send_updates(self, arr):
        data = json.dumps(arr).encode()
        arr.clear()
        self.send_data(data)


def main():
    server_scoket = server()
    server_scoket.socket.bind(settings.SERVER_ADDRESS)
    arr = []
    receive_thread = threading.Thread(target=server_scoket.receive_packets, args=(arr,))
    handling_thread = threading.Thread(target=server_scoket.handle_updates, args=(arr,))
    receive_thread.start()
    handling_thread.start()
    while True:
        time.sleep(settings.UPDATE_TICK)
        server_scoket.send_updates(arr)


if __name__ == '__main__':
    main()
