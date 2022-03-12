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

    def add(self, address, game_state):
        self.clients.append(address)
        data = json.dumps({'cmd': 'new', 'id': self.clientsAmount, 'entitles': game_state})
        self.clientsAmount += 1
        self.socket.sendto(data.encode(), address)

    def remove(self, address):
        self.clients.remove(address)
        print("Client {} disconnected".format(address))
        self.clientsAmount -= 1

    def send_data(self, data):
        for i in self.clients:
            try:
                self.socket.sendto(data, i)
            except Exception:
                print("Cant send to: {}".format(i))

    def receive_packets(self, arr):
        while True:
            try:
                (msg, client_address) = self.socket.recvfrom(settings.HEADER_SIZE)
                print("received packet. address: {}".format(client_address))
                try:
                    data = json.loads(msg.decode())
                except Exception:
                    data = "Cant load data"
                print("data: {}".format(data))
                if client_address not in self.clients and "cmd" in data and data["cmd"] == "new":
                    self.add(client_address, arr)
                elif "cmd" in data and data["cmd"] == "disconnect":
                    self.remove(client_address)
                else:
                    arr.append(data)
                    print(arr)
            except Exception:
                continue
                print("Cant receive")

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
