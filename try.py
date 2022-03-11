import json
import time
import threading
import socket
import settings


class server:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ip = socket.gethostbyname(socket.gethostname())
        self.port = settings.SERVER_PORT
        self.clients = []
        self.clientsAmount = 0
        self.address = (self.ip, self.port)

    def add(self, address):
        self.clients.append(address)
        self.clientsAmount += 1
        data = json.dumps({'cmd': 'new', 'id': self.clientsAmount})
        self.socket.sendto(data.encode(), address)

    def send_data(self, data):
        for i in self.clients:
            self.socket.sendto(data, i)

    def receive_packets(self, arr):
        while True:
            msg, client_address = self.socket.recvfrom(settings.HEADER_SIZE)
            if client_address not in self.clients:
                self.add(client_address)
            try:
                data = json.loads(msg.decode())
                arr.append(data)
            except Exception:
                continue

    def handle_updates(self, arr):
        pass

    def send_updates(self, arr):
        threading.Timer(settings.GAME_TICK, self.send_updates).start()
        data = json.dumps(arr).encode()
        self.send_data(data)
        arr.clear()


def main():
    server_scoket = server()
    arr = []
    receive_thread = threading.Thread(target=server_scoket.receive_packets, args=(arr,))
    handling_thread = threading.Thread(target=server_scoket.handle_updates, args=(arr,))
    receive_thread.start()
    handling_thread.start()
    server_scoket.send_updates(arr)


if __name__ == '__main__':
    main()
