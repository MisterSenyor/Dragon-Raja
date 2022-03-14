import json
import logging
import socket
import threading
import time

import settings


class Server:
    def __init__(self, sock: socket.socket):
        self.socket = sock
        self.clients = []

        self.entities = {}
        self.updates = []

        logging.debug(f'server listening at: {self.socket.getsockname()}')

    def connect(self, data, address):
        self.clients.append(address)
        entity = data['entity']

        data = json.dumps(
            {'cmd': 'connect', 'id': entity['id'], 'entitles': list(self.entities.values()), 'projectiles': []})
        data = data.encode() + b'\n'
        self.socket.sendto(data, address)

        self.entities[entity['id']] = entity
        self.updates.append({'cmd': 'new', 'entity': entity})

        logging.debug(f'new client connected: {self.clients=}, {self.entities=}')

    def disconnect(self, data, address):
        self.clients.remove(address)
        del self.entities[data['id']]
        self.updates.append(data)

        logging.debug(f'client disconnected: {self.clients=}, {self.entities=}')

    def send_data(self, data):
        for addr in self.clients:
            try:
                self.socket.sendto(data, addr)
            except Exception:
                logging.exception(f"can't send data to client: {addr=}, {data=}")

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(settings.HEADER_SIZE)
                data = json.loads(msg.decode())

                logging.debug(f'received data: {data=}')
                if data["cmd"] == "connect":
                    if address not in self.clients:
                        self.connect(data=data, address=address)
                elif data["cmd"] == "disconnect":
                    self.disconnect(data=data, address=address)
                else:
                    self.updates.append(data)
            except Exception:
                logging.exception('exception while handling request')

    def send_updates(self):
        data = json.dumps({'cmd': 'update', 'updates': self.updates}).encode() + b'\n'
        self.updates.clear()
        self.send_data(data)


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(settings.SERVER_ADDRESS)

    server = Server(sock=sock)
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        server.send_updates()


if __name__ == '__main__':
    main()
