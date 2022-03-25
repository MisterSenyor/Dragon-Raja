import json
import logging
import random
import socket
import threading
import time
from dataclasses import dataclass
from typing import Tuple, List, Dict

import settings


class MyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (Entity, Item, Projectile)):
            return o.__dict__
        return super(MyJSONEncoder, self).default(o)


@dataclass
class Entity:
    id: int
    start_pos: Tuple[int, int]
    end_pos: Tuple[int, int]
    t0: int
    health: int


@dataclass
class Item:
    item_type: str
    t0: int


@dataclass
class Player(Entity):
    items: List[Item]
    username: str


@dataclass
class Projectile:
    target: Tuple[int, int]
    type: str
    attacker_id: int


class Server:
    def __init__(self, sock: socket.socket):
        self.socket = sock
        self.clients = []

        self.players: Dict[int, Player] = {}
        self.projectiles: List[Projectile] = []
        self.updates = []

        logging.debug(f'server listening at: {self.socket.getsockname()}')

    def connect(self, data, address):
        player = Player(id=random.randint(0, 99999), start_pos=(1400, 1360), end_pos=(1400, 1360),
                        health=100, items=[], t0=0, username=data['username'])
        self.updates.append({'cmd': 'player_enters', 'player': player})

        data = json.dumps({
            'cmd': 'init',
            'main_player': player,
            'players': list(self.players.values()),
            'projectiles': self.projectiles
        }, cls=MyJSONEncoder).encode() + b'\n'
        self.socket.sendto(data, address)

        self.clients.append(address)
        self.players[player.id] = player

        logging.debug(f'new client connected: {address=}, {player=}')

    def disconnect(self, data, address):
        self.clients.remove(address)

        del self.players[data['id']]
        self.updates.append({'cmd': 'player_leaves', 'id': data['id']})

        logging.debug(f'client disconnected: {address=}, {data=}')

    def send_data(self, data):
        for addr in self.clients:
            try:
                self.socket.sendto(data, addr)
            except Exception:
                logging.exception(f"can't send data to client: {addr=}, {data=}")

    def handle_update(self, data, address):
        self.updates.append(data)

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
                    self.handle_update(data=data, address=address)
            except Exception:
                logging.exception('exception while handling request')

    def send_updates(self):
        data = json.dumps({'cmd': 'update', 'updates': self.updates}, cls=MyJSONEncoder).encode() + b'\n'
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
