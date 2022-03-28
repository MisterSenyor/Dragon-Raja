import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

from scipy.spatial import KDTree

import settings
from utils import *


class MyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, MovingObject):
            t = time.time_ns()
            data = o.__dict__.copy()
            del data['t0']
            data['start_pos'] = o.get_pos(t)
            return data
        return super(MyJSONEncoder, self).default(o)


@dataclass
class Item:
    item_type: str
    t0: int


@dataclass
class MovingObject(ABC):
    id: Optional[int]
    start_pos: Tuple[int, int]
    t0: int

    def __post_init__(self):
        if self.id is None:
            self.id = random.randint(0, 99999)

    @abstractmethod
    def get_pos(self, t: int = None):
        pass

    @abstractmethod
    def get_speed(self):
        pass


@dataclass
class Entity(MovingObject, ABC):
    end_pos: Optional[Tuple[int, int]]
    health: int
    items: List[Item]

    def __post_init__(self):
        super(Entity, self).__post_init__()
        if self.end_pos is None:
            self.end_pos = tuple(self.start_pos)

    def move(self, pos: Tuple[int, int], t: int = None):
        t = t if t is not None else time.time_ns()
        curr_pos = self.get_pos(t)
        self.start_pos, self.end_pos = curr_pos, pos
        self.t0 = t

    def get_pos(self, t: int = None):
        t = t if t is not None else time.time_ns()
        dist = ((self.end_pos[0] - self.start_pos[0]) ** 2 + (self.end_pos[1] - self.start_pos[1]) ** 2) ** 0.5
        if dist == 0:
            return self.start_pos
        norm_speed = 100 * self.get_speed() * 10 ** -9  # speed / 1 game tick = speed / (100 * 10 ** -9 nanosecs)
        total_time = dist / norm_speed
        p = (t - self.t0) / total_time
        if p > 1:
            return self.end_pos
        return round(self.end_pos[0] * p + self.start_pos[0] * (1 - p)), round(
            self.end_pos[1] * p + self.start_pos[1] * (1 - p))


@dataclass
class Player(Entity):
    username: str

    def get_damage(self):
        return 20

    def get_speed(self):
        return 5


@dataclass
class Projectile(MovingObject):
    target: Tuple[int, int]
    type: str
    attacker_id: int

    def get_pos(self, t: int = None):
        t = t if t is not None else time.time_ns()
        dist = (self.target[0] ** 2 + self.target[1] ** 2) ** 0.5
        norm_speed = 100 * self.get_speed() * 10 ** -9  # speed / 1 game tick = speed / (100 * 10 ** -9 nanosecs)
        total_time = dist / norm_speed
        p = (t - self.t0) / total_time
        return round(self.target[0] * p + self.start_pos[0]), round(self.target[1] * p + self.start_pos[1])

    def get_speed(self):
        return 10

    def get_damage(self):
        return 20


@dataclass
class Mob(Entity):
    def get_speed(self):
        return 2


class Server:
    def __init__(self, sock: socket.socket):
        self.socket = sock
        self.clients = []

        self.players: Dict[int, Player] = {}
        self.mobs: Dict[int, Mob] = {}
        self.projectiles: Dict[int, Projectile] = {}
        self.updates = []
        self.attacking_players: List[int] = []  # attacking players' ids

        self.generate_mobs(20)

        logging.debug(f'server listening at: {self.socket.getsockname()}')

    def generate_mobs(self, count):
        for _ in range(count):
            m = Mob(id=None, start_pos=(random.randint(1000, 2000), random.randint(1000, 2000)), end_pos=None,
                    health=100, t0=0, items=[])
            self.mobs[m.id] = m

    def update_mobs(self):
        t = time.time_ns()
        if random.random() < 0.01:
            m = random.choice(list(self.mobs.values()))
            pos = m.get_pos(t)
            m.move(t=t, pos=(pos[0] + random.randint(100, 500), pos[1] + random.randint(100, 500)))
            logging.debug(f'mob moved: {m=}')
            self.updates.append({'cmd': 'move', 'pos': m.end_pos, 'id': m.id})
        if random.random() < 0.01:
            m = random.choice(list(self.mobs.values()))
            target = random.randint(-100, 100), random.randint(-100, 100)
            proj = Projectile(id=None, t0=t, start_pos=m.get_pos(t), target=target, type='axe', attacker_id=m.id)
            self.projectiles[proj.id] = proj
            logging.debug(f'mob shot projectile: {m=}, {proj=}')
            self.updates.append({'cmd': 'projectile', 'projectile': proj, 'id': m.id})

    def connect(self, data, address):
        player = Player(id=None, start_pos=(1400, 1360), end_pos=None,
                        health=100, items=[], t0=0, username=data['username'])
        self.updates.append({'cmd': 'player_enters', 'player': player})

        data = json.dumps({
            'cmd': 'init',
            'main_player': player,
            'players': list(self.players.values()),
            'mobs': list(self.mobs.values()),
            'projectiles': self.projectiles
        }, cls=MyJSONEncoder).encode() + b'\n'
        send_all(self.socket, data, address)

        self.clients.append(address)
        self.players[player.id] = player

        logging.debug(f'new client connected: {address=}, {player=}')

    def disconnect(self, data, address):
        self.clients.remove(address)

        del self.players[data['id']]
        self.updates.append({'cmd': 'player_leaves', 'id': data['id']})

        logging.debug(f'client disconnected: {address=}, {data=}')

    def deal_damage(self, entity: Entity, damage: int):
        entity.health -= damage
        if entity.health < 0:
            if isinstance(entity, Player):
                del self.players[entity.id]
            elif isinstance(entity, Mob):
                del self.mobs[entity.id]
            logging.debug(f'entity died: {entity=}')

    def handle_collision(self, o1, o2) -> bool:
        result = False
        if isinstance(o1, Projectile) and isinstance(o2, Entity):
            result = self.handle_collision(o2, o1)
        if isinstance(o1, Entity) and isinstance(o2, Projectile):
            entity, proj = o1, o2
            if proj.attacker_id != entity.id:
                result = True
                logging.debug(f'entity-projectile collision: {entity=}, {proj=}')
                logging.debug(f'{entity.get_pos()=}, {proj.get_pos()=}')
                if proj.id in self.projectiles:
                    del self.projectiles[proj.id]
                self.deal_damage(entity, proj.get_damage())
        if isinstance(o1, Player) and isinstance(o2, Entity):
            if o1.id in self.attacking_players:
                result = True
                self.deal_damage(o2, o1.get_damage())
        if isinstance(o1, Entity) and isinstance(o2, Player):
            if o2.id in self.attacking_players:
                result = True
                self.deal_damage(o1, o2.get_damage())
        return result

    def collisions_handler(self):
        t = time.time_ns()
        moving_objs: List[MovingObject] = list(self.players.values()) + list(self.mobs.values()) + list(self.projectiles.values())
        if not moving_objs:
            return
        data = [o.get_pos(t) for o in moving_objs]
        kd_tree = KDTree(data)
        collisions = kd_tree.query_pairs(100)
        relevant_collisions = []
        for col in collisions:
            o1, o2 = moving_objs[col[0]], moving_objs[col[1]]
            if self.handle_collision(o1, o2):
                relevant_collisions.append([o1.id, o2.id])
        self.attacking_players = []
        if relevant_collisions:
            self.updates.append({'cmd': 'collisions', 'collisions': relevant_collisions})

    def handle_update(self, data, address):
        cmd = data['cmd']
        player = self.players[data['id']]
        t = time.time_ns()
        if cmd == 'move':
            player.move(data['pos'])
        elif cmd == 'projectile':
            proj = Projectile(**data['projectile'], start_pos=player.get_pos(t), t0=t, id=None)
            self.projectiles[proj.id] = proj
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
        for client in self.clients:
            send_all(self.socket, data, client)


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(settings.SERVER_ADDRESS)

    server = Server(sock=sock)
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        server.update_mobs()
        server.collisions_handler()
        server.send_updates()


if __name__ == '__main__':
    main()
