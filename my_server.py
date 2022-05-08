import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from os import path
from typing import List, Optional

import pygame
import pygame as pg
from scipy.spatial import KDTree

import settings
from Tilemap import TiledMap
from server_chat import *
from utils import *

pg.display.set_mode((40, 40))


def default_player(username):
    items = {str(generate_id()): "speed_pot", str(generate_id()): "heal_pot", str(generate_id()): "strength_pot"}
    cooldowns = {action: Cooldown(duration=duration, t0=0) for action, duration in COOLDOWN_DURATIONS.items()}
    return Player(id=None, start_pos=(1400, 1360), end_pos=None,
                  health=100, items=items, t0=0, username=username, effects=[], cooldowns=cooldowns)


def game_ticks_to_ns(game_ticks: int):
    return game_ticks / (10 ** -9) / FPS


def collision_align(pos_before1: tuple, pos_after1: tuple, size1: tuple, pos_before2: tuple, pos_after2: tuple,
                    size2: tuple) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    before1 = pg.Rect(pos_before1, size1)
    after1 = pg.Rect(pos_after1, size1)
    before2 = pg.Rect(pos_before2, size2)
    after2 = pg.Rect(pos_after2, size2)

    if after1.colliderect(after2):
        if before1 == after1 and before2 != after2:
            aligned2, aligned1 = collision_align(pos_before1=pos_before2, pos_after1=pos_after2, size1=size2,
                                                 pos_before2=pos_before1, pos_after2=pos_after1, size2=size1)
            return aligned1, aligned2
        if before1 == after1:
            after1.x += 1

        m, n = None, None
        if after1.x != before1.x:
            m = (after1.y - before1.y) / (after1.x - before1.x)
            n = before1.y - m * before1.x

        if after1.x > before1.x:
            after1.right = before2.left
        elif after1.x < before1.x:
            after1.left = before2.right

        if after1.y > before1.y:
            after1.bottom = before2.top
        elif after1.y < before1.y:
            after1.top = before2.bottom

        if m is None or m == 0:
            return after1.topleft, after2.topleft

        y1 = round(m * after1.x + n)
        x2 = round((after1.y - n) / m)

        tmp1 = pygame.Vector2(after1.x, y1)
        tmp2 = pygame.Vector2(x2, after1.y)

        if pygame.Vector2(tmp1).distance_squared_to(before1.topleft) < pygame.Vector2(tmp2).distance_squared_to(
                before1.topleft):
            return (after1.x, y1), after2.topleft
        return (x2, after1.y), after2.topleft
    return after1.topleft, after2.topleft


def player_from_dict(data: dict):
    if 'effects' in data:
        effects = [Effect(duration=e['duration'], t0=time.time_ns(), type=e['type']) for e in data.pop('effects')]
    else:
        effects = []
    if 'cooldowns' in data:
        cooldowns = {action: Cooldown(duration=c['duration'], t0=time.time_ns()) for action, c
                     in data.pop('cooldowns').items()}
    else:
        cooldowns = {action: Cooldown(duration=duration, t0=time.time_ns()) for action, duration
                     in COOLDOWN_DURATIONS.items()}
    items = data.pop('items') if 'items' in data else {}
    p = Player(**data, t0=time.time_ns(), effects=effects, cooldowns=cooldowns, items=items)
    return p


def json_encode(player, items=False, cooldowns=False, effects=False, todict=False):
    class MyJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, MovingObject):
                t = time.time_ns()
                data = o.__dict__.copy()
                del data['t0']
                data['start_pos'] = o.get_pos(t)
                if isinstance(o, Player):
                    if not items:
                        del data['items']
                    if not effects:
                        del data['effects']
                    if not cooldowns:
                        del data['cooldowns']
                return data
            if isinstance(o, Dropped):
                return o.__dict__.copy()
            if isinstance(o, Cooldown):
                data = o.__dict__.copy()
                data['duration'] -= time.time_ns() - data.pop('t0')
                return data
            return super(MyJSONEncoder, self).default(o)

    data = json.dumps(player, cls=MyJSONEncoder).encode()
    if todict:
        return json.loads(data)
    return data


@dataclass
class Dropped:
    item_id: str
    item_type: str
    pos: Tuple[int, int]


class Hitbox(ABC):
    @abstractmethod
    def get_size(self):
        pass

    @abstractmethod
    def get_pos(self, t=None):
        return None


@dataclass
class Wall(Hitbox):
    size: Tuple[int, int]
    pos: Tuple[int, int]

    def __post_init__(self):
        self.size = round(self.size[0]), round(self.size[1])
        self.pos = round(self.pos[0]), round(self.pos[1])

    def get_size(self):
        return self.size

    def get_pos(self, t=None):
        return self.pos


@dataclass
class MovingObject(Hitbox):
    id: Optional[int]
    start_pos: Tuple[int, int]
    t0: int

    def __post_init__(self):
        if self.id is None:
            self.id = generate_id()

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

    def get_size(self):
        return PLAYER_SIZE

    def reset_cooldown(self, cooldown_name):
        self.cooldowns[cooldown_name].t0 = time.time_ns()
        self.cooldowns[cooldown_name].duration = COOLDOWN_DURATIONS[cooldown_name] * 10 ** 9  # secs to ns


@dataclass
class Projectile(MovingObject):
    target: Tuple[int, int]
    type: str
    attacker_id: int

    def get_pos(self, t: int = None):
        t = t if t is not None else time.time_ns()
        dist = (self.target[0] ** 2 + self.target[1] ** 2) ** 0.5
        norm_speed = self.get_speed() / game_ticks_to_ns(1)
        total_time = dist / norm_speed
        p = (t - self.t0) / total_time
        return round(self.target[0] * p + self.start_pos[0]), round(self.target[1] * p + self.start_pos[1])

    def get_speed(self):
        return 10

    def get_damage(self):
        return 20

    def get_size(self):
        return PROJECTILE_SIZE


@dataclass
class Mob(Entity):
    type: str

    def get_speed(self):
        return 2

    def get_size(self):
        return MOB_SIZE

    def get_damage(self):
        return 20


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
        self.clients = set()

        self.players: Dict[int, Player] = {}
        self.mobs: Dict[int, Mob] = {}
        self.walls: List[Wall] = []

        self.projectiles: Dict[int, Projectile] = {}
        self.dropped: Dict[str, Dropped] = {}
        self.updates = []
        self.attacking_entities: List[int] = []  # attacking entity ids

        map_folder = 'maps'
        self.map = TiledMap(path.join(map_folder, 'map_new.tmx'))
        for wall in self.map.get_objects(apply_func=lambda x: x):
            self.walls.append(Wall(size=wall[1], pos=wall[0]))

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
            proj = Projectile(id=None, start_pos=mob_pos, target=target, type='axe', attacker_id=mob.id,
                              t0=time.time_ns())
            self.projectiles[proj.id] = proj
            self.updates.append({'cmd': 'projectile', 'projectile': proj, 'id': mob.id})
        elif mob.type == 'demon':
            self.updates.append({'cmd': 'attack', 'id': mob.id})
            self.attacking_entities.append(mob.id)

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

        data = {
            'cmd': 'init',
            'main_player': json_encode(player, items=True, todict=True),
            'players': list(self.players.values()),
            'mobs': list(self.mobs.values()),
            'projectiles': list(self.projectiles.values()),
            'dropped': list(self.dropped.values())
        }
        send_all(self.socket, json_encode(data), address)

        self.clients.add(address)
        self.players[player.id] = player

        logging.debug(f'new client connected: {address=}, {player=}')

    def disconnect(self, data, address):
        self.clients.remove(address)

        del self.players[data['id']]
        self.updates.append({'cmd': 'player_leaves', 'id': data['id']})

        logging.debug(f'client disconnected: {address=}, {data=}')

    def handle_death(self, entity: Entity):
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
        logging.debug(f'entity died: {entity=}')

    def deal_damage(self, entity: Entity, damage: int):
        entity.health -= damage
        if entity.health <= 0:
            self.handle_death(entity)

    def get_collision_data(self, o1, o2):
        if not isinstance(o1, Entity) and not isinstance(o2, Entity):
            return {}
        if not isinstance(o1, Entity):
            return self.get_collision_data(o2, o1)

        id2 = o2.id if isinstance(o2, (Entity, Projectile)) else None
        result = {'id1': o1.id, 'id2': id2, 'aligned1': None, 'aligned2': None, 'damage1': 0, 'damage2': 0}

        collision = dist(o1.get_pos(), o2.get_pos()) < 50

        if isinstance(o2, Projectile) and collision:
            if o2.attacker_id != o1.id:
                result['damage1'] = o2.get_damage()
                return result
            return {}

        t = time.time_ns()
        t2 = t + game_ticks_to_ns(10)
        pos_after1, pos_after2 = o1.get_pos(t2), o2.get_pos(t2)
        aligned1, aligned2 = collision_align(pos_before1=o1.get_pos(t), pos_before2=o2.get_pos(t),
                                             pos_after1=pos_after1,
                                             pos_after2=pos_after2, size1=o1.get_size(), size2=o2.get_size())
        if tuple(aligned1) != tuple(pos_after1):
            result['aligned1'] = aligned1
        if tuple(aligned2) != tuple(pos_after2):
            result['aligned2'] = aligned2

        if isinstance(o1, Entity) and isinstance(o2, Entity) and collision:
            if o1.id in self.attacking_entities:
                result['damage2'] = o1.get_damage()
            if o2.id in self.attacking_entities:
                result['damage1'] = o2.get_damage()

        if result['aligned1'] is not None or result['aligned2'] is not None or result['damage1'] > 0 or \
                result['damage2'] > 0:
            return result
        return {}

    def handle_collision(self, collision_data):
        id1, id2 = collision_data['id1'], collision_data['id2']
        o1, o2 = None, None
        if id1 in self.players:
            o1 = self.players[id1]
        elif id1 in self.mobs:
            o1 = self.mobs[id1]
        elif id1 in self.projectiles:
            o1 = self.projectiles[id1]
        if id2 in self.players:
            o2 = self.players[id2]
        elif id2 in self.mobs:
            o2 = self.mobs[id2]
        elif id2 in self.projectiles:
            o2 = self.projectiles[id2]

        if o1 is not None and collision_data['aligned1'] is not None:
            o1.end_pos = collision_data['aligned1']
        if o2 is not None and collision_data['aligned2'] is not None:
            o2.end_pos = collision_data['aligned2']

        if o1 is not None and isinstance(o1, Entity):
            self.deal_damage(o1, collision_data['damage1'])
        if o2 is not None and isinstance(o2, Entity):
            self.deal_damage(o2, collision_data['damage2'])
        elif o2 is not None and isinstance(o2, Projectile):
            del self.projectiles[o2.id]

    def collisions_handler(self):
        t = time.time_ns()
        hitboxes: List[Hitbox] = list(self.players.values()) + list(self.mobs.values()) + list(
            self.projectiles.values()) + self.walls

        positions = [hitbox.get_pos(t) for hitbox in hitboxes]
        kd_tree = KDTree(positions)
        collisions = kd_tree.query_pairs(100)

        collisions_data = []
        for col in collisions:
            o1, o2 = hitboxes[col[0]], hitboxes[col[1]]
            collision_data = self.get_collision_data(o1, o2)
            if collision_data:
                collisions_data.append(collision_data)
                self.handle_collision(collision_data)
        self.attacking_entities = []
        if collisions_data:
            self.updates.append({'cmd': 'collisions', 'collisions_data': collisions_data})

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
            player.reset_cooldown('projectile')
            self.projectiles[proj.id] = proj
            data['projectile'] = proj  # add id field
        elif cmd == 'attack':
            self.attacking_entities.append(player.id)
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
            data['extra'] = {}
            if not player.cooldowns['skill'].is_over():
                return
            logging.debug(f"{player.cooldowns['skill']=}")
            if data['skill_id'] == 1:
                vect = pg.math.Vector2(0, 1)
                projectile_ids = []
                for i in range(0, 9):
                    # CIRCLE OF AXES:
                    axe = Projectile(id=None, start_pos=player.get_pos(t), type="axe", attacker_id=player.id, t0=t,
                                     target=tuple(vect))
                    self.projectiles[axe.id] = axe
                    projectile_ids.append(axe.id)
                    vect = vect.rotate(45)
                data['extra']['projectile_ids'] = projectile_ids
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
            player.reset_cooldown('skill')
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
                'entities': [{'id': entity.id, 'pos': entity.get_pos()} for entity in list(self.players.values()) +
                             list(self.mobs.values())]
            })
        data = json_encode({'cmd': 'update', 'updates': self.updates})
        self.updates.clear()
        for client in self.clients:
            send_all(self.socket, data, client)


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(settings.SERVER_ADDRESS)

    server = Server(sock=sock)
    server.generate_mobs(settings.MOB_COUNT)
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()
    # INITIALIZE CHAT SERVER:
    server_chat = ChatServer()
    threading.Thread(target=server_chat.start).start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        server.update_mobs()
        server.collisions_handler()
        server.send_updates()


if __name__ == '__main__':
    main()
