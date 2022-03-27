import abc
import json
import logging
import random
import socket
import threading
import time
from dataclasses import dataclass
from typing import Tuple, List, Dict

from scipy.spatial import KDTree

import settings


class MyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Projectile):
            return {'type': o.type, 'target': o.target, 'attacker_id': o.attacker_id}
        elif isinstance(o, Entity):
            data = o.__dict__.copy()
            data['end_pos'] = data.pop('target')
            return data
        elif isinstance(o, Item):
            return o.__dict__
        return super(MyJSONEncoder, self).default(o)


@dataclass
class MovingObject(abc.ABC):
    start_pos: Tuple[int, int]
    t0: int
    target: Tuple[int, int]

    def get_movement_part(self, t: int = None):
        t = t if t is not None else time.time_ns()
        dist = ((self.target[0] - self.start_pos[0]) ** 2 + (self.target[1] - self.start_pos[1]) ** 2) ** 0.5
        total_time = dist / self.get_speed()
        return (t - self.t0) / total_time

    def get_pos(self, t: int = None):
        p = self.get_movement_part(t)
        return round(self.target[0] * p + self.start_pos[0] * (1 - p)), round(
            self.target[1] * p + self.start_pos[1] * (1 - p))

    @abc.abstractmethod
    def get_speed(self):
        pass


@dataclass
class Entity(MovingObject):
    id: int
    health: int

    def move(self, target: Tuple[int, int], t: int = None):
        t = t if t is not None else time.time_ns()
        curr_pos = self.get_pos(t)
        self.start_pos, self.target = curr_pos, target
        self.t0 = t

    def get_pos(self, t: int = None):
        t = t if t is not None else time.time_ns()
        if self.target == self.start_pos:
            return self.start_pos
        p = self.get_movement_part(t)
        if p > 1:
            return self.target
        return super(Entity, self).get_pos(t)

    def get_speed(self):
        return 100 * 5 * 10 ** -9


@dataclass
class Item:
    item_type: str
    t0: int


@dataclass
class Player(Entity):
    items: List[Item]
    username: str

    def get_damage(self):
        return 20


@dataclass
class Projectile(MovingObject):
    type: str
    attacker_id: int

    def get_speed(self):
        return 10 * 10 * 10 ** -9

    def get_damage(self):
        return 20


class Server:
    def __init__(self, sock: socket.socket):
        self.socket = sock
        self.clients = []

        self.players: Dict[int, Player] = {}
        self.projectiles: List[Projectile] = []
        self.updates = []
        self.attacking_players: List[int] = []  # attacking players' ids

        logging.debug(f'server listening at: {self.socket.getsockname()}')

    def connect(self, data, address):
        player = Player(id=random.randint(0, 99999), start_pos=(1400, 1360), target=(1400, 1360),
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

    def deal_damage(self, player: Player, damage: int):
        player.health -= damage
        if player.health < 0:
            del self.players[player.id]
            logging.debug(f'player died: {player=}')


    def handle_collision(self, o1: MovingObject, o2: MovingObject):
        if isinstance(o1, Projectile) and isinstance(o2, Player):
            self.handle_collision(o2, o1)
        elif isinstance(o1, Player) and isinstance(o2, Projectile):
            player, proj = o1, o2
            if proj.attacker_id != player.id:
                logging.debug(f'player-projectile collision: {player=}, {proj=}')
                self.projectiles.remove(proj)
                self.deal_damage(player, proj.get_damage())
        elif isinstance(o1, Player) and isinstance(o2, Player):
            if o1.id in self.attacking_players:
                self.deal_damage(o2, o1.get_damage())
            if o2.id in self.attacking_players:
                self.deal_damage(o1, o2.get_damage())
        self.attacking_players = []

    def collisions_handler(self):
        t = time.time_ns()
        moving_objs: List[MovingObject] = list(self.players.values()) + self.projectiles
        if not moving_objs:
            return
        data = [o.get_pos(t) for o in moving_objs]
        kd_tree = KDTree(data)
        collisions = kd_tree.query_pairs(300)
        for col in collisions:
            self.handle_collision(moving_objs[col[0]], moving_objs[col[1]])

    def handle_update(self, data, address):
        cmd = data['cmd']
        player = self.players[data['id']]
        t = time.time_ns()
        if cmd == 'move':
            player.move(data['pos'])
        elif cmd == 'projectile':
            self.projectiles.append(Projectile(**data['projectile'], start_pos=player.get_pos(t), t0=t))
        elif cmd == 'attack':
            self.attacking_players.append(player.id)
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
        server.collisions_handler()
        server.send_updates()


if __name__ == '__main__':
    main()
