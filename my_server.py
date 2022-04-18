import logging
import math
import random
import threading
import time
import pygame as pg
from Tilemap import TiledMap
from abc import ABC, abstractmethod
from os import path
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

import pygame as pg
from scipy.spatial import KDTree

import settings
# from server_chat import chat_server
from server_chat import *
from utils import *

pg.display.set_mode((40, 40))


def default_player(username):
    items = {str(generate_id()): "speed_pot", str(generate_id()): "heal_pot", str(generate_id()): "strength_pot"}
    cooldowns = {'skill': Cooldown(duration=0, t0=0), 'projectile': Cooldown(duration=0, t0=0)}
    return MainPlayer(id=None, start_pos=(1400, 1360), end_pos=None,
                      health=100, items=items, t0=0, username=username, effects=[], cooldowns=cooldowns)


def game_ticks_to_ns(game_ticks: int):
    return game_ticks / (10 ** -9) / FPS


def check_collisions(direction: tuple, pos_before: tuple, pos_after: tuple, size: tuple, target_pos: tuple,
                     target_size: tuple) -> tuple:
    temp = pg.Rect(pos_after, size)
    hit = pg.Rect(target_pos, target_size)

    if direction[0] > 0:
        if temp.left > hit.right > pos_before[0] + size[0]:
            temp.move(hit.right - temp.left, 0)
    elif direction[0] < 0:
        if temp.right < hit.left and pos_before[0] > hit.right:
            temp.move(hit.left - temp.right, 0)

    # checking Y
    if direction[1] > 0:
        if temp.bottom > hit.top > pos_before[1] + size[1]:
            temp.move(0, hit.top - temp.bottom)
    elif direction[1] < 0:
        if temp.top < hit.bottom < pos_before[1]:
            temp.move(0, hit.bottom - temp.top)

    return temp.topright


class MyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, MovingObject):
            t = time.time_ns()
            data = o.__dict__.copy()
            del data['t0']
            data['start_pos'] = o.get_pos(t)
            if isinstance(o, Player) and not isinstance(o, MainPlayer):
                del data['items']
            return data
        if isinstance(o, Dropped):
            return o.__dict__.copy()
        if isinstance(o, Cooldown):
            data = o.__dict__.copy()
            data['duration'] -= time.time_ns() - data.pop('t0')
            return data
        return super(MyJSONEncoder, self).default(o)


def player_from_dict(data: dict):
    effects = [Effect(duration=e['duration'], t0=time.time_ns(), type=e['type']) for e in data.pop('effects')]
    cooldowns = {action: Cooldown(duration=c['duration'], t0=time.time_ns()) for action, c
                 in data.pop('cooldowns').items()}
    p = MainPlayer(**data, t0=time.time_ns(), effects=effects, cooldowns=cooldowns)
    return p


@dataclass
class Dropped:
    item_id: str
    item_type: str
    pos: Tuple[int, int]


@dataclass
class MovingObject(ABC):
    id: Optional[int]
    start_pos: Tuple[int, int]
    t0: int

    def __post_init__(self):
        if self.id is None:
            self.id = generate_id()

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
        norm_speed = self.get_speed() / game_ticks_to_ns(1)
        total_time = dist / norm_speed
        p = (t - self.t0) / total_time
        if p > 1:
            return self.end_pos
        return round(self.end_pos[0] * p + self.start_pos[0] * (1 - p)), round(
            self.end_pos[1] * p + self.start_pos[1] * (1 - p))


@dataclass
class Cooldown:
    t0: int
    duration: int

    def is_over(self, t: int = None):
        t = t if t is not None else time.time_ns()
        return t > self.t0 + self.duration


@dataclass
class Effect(Cooldown):
    type: str


@dataclass
class Player(Entity):
    username: str
    items: Dict[str, str]  # ids are numbers converted to strings, e.g "123"
    effects: List[Effect]
    cooldowns: Dict[str, Cooldown]  # action to duration (ns)

    def use_item(self, item_id: str):
        item_type = self.items.pop(item_id)
        if item_type == 'heal_pot':
            if self.health < 80:
                self.health += 20
            else:
                self.health = 100
        else:
            self.effects.append(Effect(type=item_type, t0=time.time_ns(), duration=game_ticks_to_ns(1000)))

    def check_effects(self):
        for effect in self.effects[:]:
            if effect.is_over():
                self.effects.remove(effect)

    def get_damage(self):
        self.check_effects()
        return 20 + sum([10 for x in self.effects if x.type == 'strength_pot'])

    def get_speed(self):
        self.check_effects()
        return 5 + sum([3 for x in self.effects if x.type == 'speed_pot'])


# used for encoding items
class MainPlayer(Player):
    pass


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
    type: str

    def get_speed(self):
        return 2


def generate_id(max_n=100000):
    id_ = random.randint(1, max_n)
    while id_ in generate_id.ids:
        id_ = random.randint(1, max_n)
    return id_


generate_id.ids = set()


def random_drop_pos(pos):
    return pos[0] + random.randint(-50, 50), pos[1] + random.randint(-100, 100)


class Server:
    def __init__(self, sock: socket.socket):
        self.socket = sock
        self.clients = []

        self.players: Dict[int, Player] = {}
        self.mobs: Dict[int, Mob] = {}

        self.projectiles: Dict[int, Projectile] = {}
        self.dropped: Dict[str, Dropped] = {}
        self.updates = []
        self.attacking_players: List[int] = []  # attacking players' ids
        map_folder = 'maps'
        self.map = TiledMap(path.join(map_folder, 'map_new.tmx'))

        logging.debug(f'server listening at: {self.socket.getsockname()}')

    def generate_mobs(self, count):
        for _ in range(count):
            m = Mob(id=None,
                    start_pos=(random.randint(0, settings.MAP_SIZE[0] - 1),
                               random.randint(0, settings.MAP_SIZE[1] - 1)),
                    end_pos=None,
                    health=100, t0=0, type=random.choice(['dragon', 'demon']))
            self.mobs[m.id] = m

    def mob_move(self, mob: Mob):
        if mob.type == 'dragon':
            pos = mob.get_pos()
            mob.move(pos=(pos[0] + random.randint(-500, 500), pos[1] + random.randint(-500, 500)))
            self.updates.append({'cmd': 'move', 'pos': mob.end_pos, 'id': mob.id})
        elif mob.type == 'demon':
            player = self.players[random.choice(self.players)]
            player_pos = player.get_pos()
            if dist(player_pos, mob.get_pos()) < 100:
                mob.move(pos=player_pos)
                self.updates.append({'cmd': 'move', 'pos': player_pos, 'id': mob.id})

    def mob_attack(self, mob: Mob, player: Player):
        if mob.type == 'dragon':
            player_pos, mob_pos = player.get_pos(), mob.get_pos()
            target = player_pos[0] - mob_pos[0], player_pos[1] - mob_pos[1]
            proj = Projectile(id=None, start_pos=mob_pos, target=target, type='axe', attacker_id=mob.id, t0=0)
            self.projectiles[proj.id] = proj
            self.updates.append({'cmd': 'projectile', 'projectile': proj, 'id': mob.id})
        elif mob.type == 'demon':
            self.updates.append({'cmd': 'attack', 'id': mob.id})

    def update_mobs(self):
        for _ in range(math.ceil(0.01 * len(self.mobs))):
            self.mob_move(random.choice(list(self.mobs.values())))
        if self.players and not settings.PEACEFUL_MODE:
            for _ in range(math.ceil(0.1 * len(self.mobs))):
                m = random.choice(list(self.mobs.values()))
                player = random.choice(list(self.players.values()))
                if dist(player.get_pos(), m.get_pos()) < 500:
                    self.mob_attack(mob=m, player=player)

    def connect(self, data, address):
        player = default_player(data['username'])
        self.updates.append({'cmd': 'player_enters', 'player': player})

        data = json.dumps({
            'cmd': 'init',
            'main_player': player,
            'players': list(self.players.values()),
            'mobs': list(self.mobs.values()),
            'projectiles': list(self.projectiles.values()),
            'dropped': list(self.dropped.values())
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
        if entity.health <= 0:
            pos = entity.get_pos()
            if isinstance(entity, Player):
                if entity.id in self.players:
                    del self.players[entity.id]
                    drops = []
                    for item_id, item_type in entity.items.items():
                        drops.append(Dropped(
                            item_id=item_id, item_type=item_type,
                            pos=random_drop_pos(pos)))
            elif isinstance(entity, Mob):
                if entity.id in self.mobs:
                    del self.mobs[entity.id]
                drops = [Dropped(
                    item_id=str(generate_id()),
                    item_type=random.choice(['strength_pot', 'heal_pot', 'speed_pot', 'useless_card']),
                    pos=random_drop_pos(pos))
                    for _ in range(random.randint(2, 3))]
            for drop in drops:
                self.dropped[drop.item_id] = drop
            self.updates.append({'cmd': 'entity_died', 'id': entity.id, 'drops': drops})
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

        if not isinstance(o1, Entity):
            result = self.handle_collision(o2, o1)

        if isinstance(o1, Player):
            size1 = PLAYER_SIZE
        elif isinstance(o1, Mob):
            size1 = MOB_SIZE
        if isinstance(o2, Player):
            size2 = PLAYER_SIZE
        elif isinstance(o2, Mob):
            size2 = MOB_SIZE

        t = time.time_ns()
        if isinstance(o1, Entity):
            curr_pos = o1.get_pos(t)
            game_tick = (10 ** 9) / FPS  # in ns
            next_pos = o1.get_pos(t + game_tick)
            collision_pos = check_collisions(direction, curr_pos, next_pos, size1, o2[0], o2[1])
            if collision_pos != next_pos:
                o1.end_pos = collision_pos
                result = True
        return result

    def collisions_handler(self):
        t = time.time_ns()
        moving_objs: List[MovingObject] = list(self.players.values()) + list(self.mobs.values()) + list(
            self.projectiles.values())
        if not moving_objs:
            return
        data = [o.get_pos(t) for o in moving_objs]
        data = data + [wall[0] for wall in self.map.get_objects(apply_func=lambda x: x)]
        kd_tree = KDTree(data)
        collisions = kd_tree.query_pairs(100)
        relevant_collisions = []
        o1, o2 = None, None
        for col in collisions:
            if col[0] < len(moving_objs):
                o1 = moving_objs[col[0]]
            if col[1] < len(moving_objs):
                o2 = moving_objs[col[1]]
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
            if not player.cooldowns['projectile'].is_over():
                return
            proj = Projectile(**data['projectile'], start_pos=player.get_pos(t), t0=t, id=None)
            player.cooldowns['projectile'].t0 = time.time_ns()
            player.cooldowns['projectile'].duration = 10 ** 9
            self.projectiles[proj.id] = proj
        elif cmd == 'attack':
            self.attacking_players.append(player.id)
        elif cmd == 'use_item':
            item_type = player.items[data['item_id']]
            player.use_item(data['item_id'])
            data = {'cmd': cmd, 'item_type': item_type, 'id': data['id']}
        elif cmd == 'item_dropped':
            if dist(data['pos'], player.get_pos(t)) < 250:
                item_type = player.items.pop(data['item_id'])
                dropped = Dropped(item_type=item_type, item_id=data['item_id'], pos=random_drop_pos(data['pos']))
                self.dropped[dropped.item_id] = dropped
                data = {'cmd': cmd, 'item_type': dropped.item_type, 'item_id': dropped.item_id, 'pos': dropped.pos}

        elif cmd == 'item_picked':
            dropped = self.dropped[data['item_id']]
            if dist(dropped.pos, player.get_pos(t)) < 100 and len(player.items) < settings.INVENTORY_SIZE:
                del self.dropped[data['item_id']]
                player.items[dropped.item_id] = dropped.item_type
                del data['id']
            else:
                raise Exception('bad client, cannot pickup item')
        elif cmd == 'use_skill':
            if not player.cooldowns['skill'].is_over():
                return
            logging.debug(f"{player.cooldowns['skill']=}")
            if data['skill_id'] == 1:
                vect = pg.math.Vector2(0, 1)
                for i in range(0, 9):
                    # CIRCLE OF AXES:
                    axe = Projectile(id=None, start_pos=player.get_pos(t), type="axe", attacker_id=player.id, t0=t,
                                     target=tuple(vect))
                    self.projectiles[axe.id] = axe
                    vect = vect.rotate(45)
            elif data['skill_id'] == 2:
                # BUFFS USING (INSTANTLY USED) ITEMS:
                item_id = str(generate_id())
                player.items[item_id] = 'speed_pot'
                player.use_item(item_id)

                item_id = str(generate_id())
                player.items[item_id] = 'strength_pot'
                player.use_item(item_id)

                item_id = str(generate_id())
                player.items[item_id] = 'heal_pot'
                player.use_item(item_id)
            elif data['skill_id'] == 3:
                # GET POTIONS IN INVENTORY:
                item_id = str(generate_id())
                player.items[item_id] = 'speed_pot'

                item_id = str(generate_id())
                player.items[item_id] = 'strength_pot'

                item_id = str(generate_id())
                player.items[item_id] = 'heal_pot'
            player.cooldowns['skill'].t0 = time.time_ns()
            player.cooldowns['skill'].duration = 10 * 10 ** 9
        self.updates.append(data)

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(settings.HEADER_SIZE)
                data = json.loads(decrypt_packet(msg).decode())
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
        if settings.ENABLE_SHADOWS:
            self.updates.append({
                'cmd': 'shadows',
                'players': [{'id': player.id, 'pos': player.get_pos()} for player in self.players.values()]
            })
        data = json.dumps({'cmd': 'update', 'updates': self.updates}, cls=MyJSONEncoder).encode() + b'\n'
        self.updates.clear()
        for client in self.clients:
            send_all(self.socket, data, client)


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(settings.SERVER_ADDRESS)

    server = Server(sock=sock)
    server.generate_mobs(20)
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()
    # INITIALIZE CHAT SERVER:
    server_chat = ChatServer()
    threading.Thread(target=server_chat.start).start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        server.update_mobs()
        # server.collisions_handler()
        server.send_updates()


if __name__ == '__main__':
    main()
