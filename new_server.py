import struct
import sys
import threading

from my_server import *
from settings import *


class NewServer(Server):
    def __init__(self, sock: socket.socket, lb_address, server_chunks: List[Tuple[int, int]],
                 shared_chunks: List[Tuple[int, int]]):
        super(NewServer, self).__init__(sock=sock)
        self.lb_address = lb_address

        self.id_to_fernet_address: Dict[int, Tuple[Fernet, Address]] = {}

        self.server_private_key = load_private_ecdh_key()

        self.server_chunks = server_chunks
        self.shared_chunks = shared_chunks
        self.private_chunks = [chunk for chunk in self.server_chunks if chunk not in self.shared_chunks]

        logging.debug(f'{self.private_chunks=}')

        self.forwarded_updates = []
        with open("super_secret_do_not_touch.txt", 'rb') as secret_key:
            self.lb_fernet = Fernet(secret_key.read())

    def recv_json(self) -> Tuple[dict, Any]:
        while True:
            try:
                msg, address = self.socket.recvfrom(settings.HEADER_SIZE)
                break
            except ConnectionResetError:
                pass
        if address == self.lb_address:
            data = self.lb_fernet.decrypt(msg)
            return json.loads(data), address
        player_id = int(msg[:6])
        if player_id in self.id_to_fernet_address:
            fernet = self.id_to_fernet_address[player_id][0]
            assert self.id_to_fernet_address[player_id][1] == address
            data = fernet.decrypt(msg[6:])
            json_data = json.loads(data)
            if not json_data['id'] == player_id:
                raise Exception('client tried to connect with a different id!')
            return json_data, address
        raise UnknownClientException()

    def generate_mobs(self, count):
        for _ in range(count):
            chunk = random.choice(self.private_chunks)
            pos_x = chunk[0] * CHUNK_SIZE + random.randint(0, CHUNK_SIZE - 1)
            pos_y = chunk[1] * CHUNK_SIZE + random.randint(0, CHUNK_SIZE - 1)
            m = Mob(id=None,
                    start_pos=(pos_x, pos_y),
                    end_pos=None,
                    health=100, t0=0, type=random.choice(['dragon', 'demon']))
            self.mobs[m.id] = m

    def mob_move(self, mob: Mob):
        if mob.type == 'dragon':
            pos = mob.get_pos()
            new_pos = pos[0] + random.randint(-500, 500), pos[1] + random.randint(-500, 500)
            while get_chunk(new_pos) not in self.private_chunks:
                new_pos = pos[0] + random.randint(-500, 500), pos[1] + random.randint(-500, 500)
            mob.move(pos=new_pos)
            self.updates.append({'cmd': 'move', 'pos': mob.end_pos, 'id': mob.id})
        elif mob.type == 'demon' and self.players:
            player = random.choice(list(self.players.values()))
            player_pos = player.get_pos()
            if get_chunk(player_pos) in self.private_chunks:
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

    def disconnect(self, data):
        self.remove_player(player_id=data['id'])
        self.remove_client(player_id=data['id'], send_remove_data=False)

    def add_client(self, player, client_addr, client_public_key, init):
        client_public_key = client_public_key.encode()
        client_addr = tuple(client_addr)
        if init:
            json_data = {
                'cmd': 'init',
                'main_player': json_encode(player, items=True, todict=True),
                'players': list(self.players.values()),
                'mobs': list(self.mobs.values()),
                'projectiles': list(self.projectiles.values()),
                'dropped': list(self.dropped.values())
            }
        else:
            json_data = {
                'cmd': 'get_data',
                'players': list(self.players.values()),
                'mobs': list(self.mobs.values()),
                'dropped': list(self.dropped.values())
            }
        data = json_encode(json_data)
        loaded_key = serialization.load_pem_public_key(client_public_key)
        fernet = get_fernet(loaded_key, self.server_private_key)

        self.id_to_fernet_address[player.id] = fernet, client_addr
        self.clients.add(client_addr)

        send_all(self.socket, data, client_addr, fernet)
        logging.debug(f'new client connected: {client_addr=}, {player=}')

    def connect(self, data, address):
        player = player_from_dict(data['player'])
        # self.updates.append()
        self.add_client(player, data['client'], data['client_key'], init=True)
        self.players[player.id] = player
        self.create_and_forward_update({'cmd': 'player_enters', 'player': player}, entity_id=player.id)

    def add_player(self, player_data):
        if player_data['id'] not in self.players:
            player = player_from_dict(player_data)
            self.players[player.id] = player

    def remove_player(self, player_id):
        if player_id in self.players:
            del self.players[player_id]

    def handle_lb_update(self, data, address):
        cmd = data['cmd']
        if cmd == 'player_enters':
            self.add_player(player_data=data['player'])
        elif cmd == 'player_leaves' or cmd == 'entity_died' and data['id'] in self.players:
            fernet, client_address = self.id_to_fernet_address[data['id']]
            updates = {
                'cmd': 'update',
                'updates': [data]
            }
            updates = json.dumps(updates).encode()
            send_all(sock=self.socket, data=updates, address=client_address, fernet=fernet)

            self.remove_player(player_id=data['id'])
            self.remove_client(player_id=data['id'], send_remove_data=False)
        elif cmd == 'entity_died' and data['id'] in self.mobs:
            del self.mobs[data['id']]
        else:
            # handle update without forwarding to lb
            self.handle_update(data=data, address=address)
            return
        self.updates.append(data)

    def remove_client(self, player_id, send_remove_data=True):
        if player_id in self.id_to_fernet_address:
            fernet, address = self.id_to_fernet_address[player_id]
            if send_remove_data:
                json_data = {
                    'cmd': 'remove_data',
                    'entities': [entity.id for entity in list(self.players.values()) + list(self.mobs.values()) if
                                 get_chunk(entity.get_pos()) in self.private_chunks]
                }
                send_all(self.socket, json_encode(json_data), address, fernet)
            del self.id_to_fernet_address[player_id]
            if address not in [addr for _, addr in self.id_to_fernet_address.values()] and address in self.clients:
                self.clients.remove(address)

    def handle_lb_request(self, data, address):
        cmd = data['cmd']
        if cmd == "connect":
            self.connect(data=data, address=address)
        elif cmd == 'add_client':
            self.add_client(self.players[data['id']], data['client'], data['client_key'], init=False)
        elif cmd == 'remove_client':
            self.remove_client(player_id=data['id'])
        elif cmd == 'update':
            # send updates to clients
            for update in data['updates']:
                self.handle_lb_update(data=update, address=address)

    def receive_packets(self):
        while True:
            try:
                data, address = self.recv_json()
                logging.debug(f'received data: {data=}, {address=}')
                if address == self.lb_address:
                    self.handle_lb_request(data=data, address=address)
                elif address in self.clients:
                    # forward update to lb
                    self.handle_or_forward_client_update(data=data, address=address)
                else:
                    logging.warning(
                        f'address not in clients or lb: {address=}, {self.id_to_fernet_address=}, {self.lb_address=}, '
                        f'{self.clients=}')
            except Exception:
                logging.exception('exception while handling request')

    def handle_or_forward_client_update(self, data, address):
        cmd = data['cmd']
        if cmd not in ['move', 'attack', 'projectile', 'disconnect', 'item_dropped', 'item_picked',
                       'use_item', 'use_skill']:
            logging.warning(f'unknown client cmd: {data=}, {address=}')
            return

        player = self.players[data['id']]
        chunk = get_chunk(player.get_pos())
        logging.debug(f'{chunk=}, {data=}')

        if cmd == 'disconnect':
            data['player'] = json_encode(player, items=True, todict=True)
            self.forwarded_updates.append((data, chunk))
        # when cmd is move, send update whenever any one of start_pos, end_pos is in a shared chunk
        elif chunk in self.shared_chunks or (cmd == 'move' and get_chunk(data['pos']) in self.shared_chunks):
            self.forwarded_updates.append((data, chunk))
        else:
            self.handle_update(data=data, address=address)

    def forward_updates(self):
        if self.forwarded_updates:
            logging.debug(f'{self.forwarded_updates=}')
        updates = []
        chunks = []
        moving_players = []
        for update, chunk in self.forwarded_updates:
            # whenever a player changes its section, send its data
            if update['cmd'] == 'move':
                player = self.players[update['id']]
                start_chunk, end_chunk = get_chunk(player.get_pos()), get_chunk(update['pos'])
                if start_chunk != end_chunk:
                    moving_players.append({
                        'start_chunk': start_chunk, 'end_chunk': end_chunk, 'player': player
                    })
            updates.append(update)
            chunks.append(chunk)
        if updates:
            data = json_encode({'cmd': 'forward_updates', 'updates': updates, 'chunks': chunks,
                               'moving_players': moving_players})
            send_all(self.socket, data, self.lb_address, self.lb_fernet)
            logging.debug(f'updates sent to lb: {updates=}, {chunks=}')
        self.forwarded_updates.clear()

    def send_updates(self):
        if settings.ENABLE_SHADOWS:
            self.updates.append({
                'cmd': 'shadows',
                'entities': [{'id': entity.id, 'pos': entity.get_pos()} for entity in list(self.players.values()) +
                             list(self.mobs.values())]
            })
        data = json_encode({'cmd': 'update', 'updates': self.updates})
        self.updates.clear()
        for player_id in self.id_to_fernet_address:
            fernet, address = self.id_to_fernet_address[player_id]
            send_all(self.socket, data, address, fernet)

    def create_and_forward_update(self, update, entity_id=None):
        entity = None
        if entity_id is None and 'id' not in update:
            raise Exception(f'entity_id not specified for update creation: {update=}')
        else:
            if entity_id is None:
                entity_id = update['id']

            if entity_id in self.players:
                entity = self.players[entity_id]
            elif entity_id in self.mobs:
                entity = self.mobs[entity_id]
            else:
                raise Exception(f'entity with id not found: {entity_id=}, {update=}')

        chunk = get_chunk(entity.get_pos())
        self.forwarded_updates.append((update, chunk))

    def handle_death(self, entity: Entity):
        pos = entity.get_pos()
        if isinstance(entity, Player):
            if entity.id in self.players:
                drops = []
                for item_id, item_type in entity.items.items():
                    drops.append(Dropped(
                        item_id=item_id, item_type=item_type,
                        pos=random_drop_pos(pos)))
        elif isinstance(entity, Mob):
            drops = [Dropped(
                item_id=str(generate_id()),
                item_type=random.choice(['strength_pot', 'heal_pot', 'speed_pot', 'useless_card']),
                pos=random_drop_pos(pos))
                for _ in range(random.randint(2, 3))]
        for drop in drops:
            self.dropped[drop.item_id] = drop
        logging.debug(f'entity died: {entity=}')

        update = {'cmd': 'entity_died', 'id': entity.id, 'drops': drops}
        if isinstance(entity, Player):
            update['player'] = entity

        self.create_and_forward_update(update)

    def backups_sender(self):
        while True:
            time.sleep(BACKUP_DELAY)
            players = {player_id: player for player_id, player in self.players.items() if
                       get_chunk(player.get_pos()) in self.server_chunks}
            if players:
                data = json_encode({'cmd': 'backups', 'players': players}, items=True)
                send_all(self.socket, data, self.lb_address, self.lb_fernet)
                # logging.info(f'backup sent to db: {data=}')


def main():
    logging.basicConfig(level=LOGLEVEL)

    server_idx = int(sys.argv[1])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(settings.SERVER_ADDRESSES[server_idx])

    chunk_mapping = generate_chunk_mapping()

    shared_chunks = []
    for i in range(CHUNKS_X):
        for j in range(CHUNKS_Y):
            adj = get_adj_server_idx(chunk_mapping, (i, j))
            if server_idx in adj and len(adj) > 1:
                shared_chunks.append((i, j))

    server_chunks = [(i, j) for i in range(CHUNKS_X) for j in range(CHUNKS_Y) if chunk_mapping[i][j] == server_idx]
    logging.debug(f'{CHUNKS_X=}, {CHUNKS_Y=}, {server_idx=}')
    logging.debug(f'{server_chunks=}')
    logging.debug(f'{shared_chunks=}')
    logging.debug(f'{chunk_mapping=}')
    logging.debug(f'{len(shared_chunks)=}, {len(server_chunks)=}')

    server = NewServer(sock=sock, lb_address=LB_ADDRESS, shared_chunks=shared_chunks, server_chunks=server_chunks)
    server.generate_mobs(MOB_COUNT)

    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()

    backups_thread = threading.Thread(target=server.backups_sender)
    backups_thread.start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        server.collisions_handler()
        server.send_updates()
        server.update_mobs()
        server.forward_updates()


if __name__ == '__main__':
    main()
