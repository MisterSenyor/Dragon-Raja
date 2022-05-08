import sys
import threading

from my_server import *
from settings import *


class NewServer(Server):
    def __init__(self, sock: socket.socket, lb_address, server_chunks: List[Tuple[int, int]],
                 shared_chunks: List[Tuple[int, int]]):
        super(NewServer, self).__init__(sock=sock)
        self.lb_address = lb_address

        self.fernets: Dict[bytes, Fernet] = {}  # client public key to fernet
        self.client_public_keys: Dict[Address, bytes] = {}  # client address to public key
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
        public_key, data = get_pk_and_data(msg)
        if public_key in self.fernets:
            data = self.fernets[public_key].decrypt(data)
            json_data = json.loads(data)
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

    def disconnect(self, data):
        self.remove_player(data)
        self.remove_client(data['address'], send_remove_data=False)

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
        self.client_public_keys[client_addr] = client_public_key
        self.fernets[client_public_key] = fernet

        send_all(self.socket, data, client_addr, self.fernets[self.client_public_keys[client_addr]])
        logging.debug(f'new client connected: {client_addr=}, {player=}')

    def connect(self, data, address):
        player = player_from_dict(data['player'])
        self.updates.append({'cmd': 'player_enters', 'player': player})
        self.add_client(player, data['client'], data['client_key'], init=True)
        self.players[player.id] = player

    def add_player(self, data):
        if data['player']['id'] not in self.players:
            player = player_from_dict(data['player'])
            self.players[player.id] = player

    def remove_player(self, data):
        if data['id'] in self.players:
            del self.players[data['id']]

    def handle_lb_update(self, data, address):
        cmd = data['cmd']
        if cmd == 'player_enters':
            self.add_player(data)
        elif cmd == 'player_leaves':
            self.remove_player(data)
            self.remove_client(tuple(data['address']), send_remove_data=False)
        else:
            # handle update without forwarding to lb
            self.handle_update(data=data, address=address)

    def remove_client(self, address, send_remove_data=True):
        if address in self.client_public_keys:
            if send_remove_data:
                json_data = {
                    'cmd': 'remove_data',
                    'entities': [entity.id for entity in list(self.players.values()) + list(self.mobs.values()) if
                                 get_chunk(entity.get_pos()) in self.private_chunks]
                }
                send_all(self.socket, json_encode(json_data), address, self.fernets[self.client_public_keys[address]])
            del self.fernets[self.client_public_keys[address]]
            del self.client_public_keys[address]

    def handle_lb_request(self, data, address):
        cmd = data['cmd']
        if cmd == "connect":
            self.connect(data=data, address=address)
        elif cmd == 'add_client':
            self.add_client(self.players[data['id']], data['client'], data['client_key'], init=False)
        elif cmd == 'remove_client':
            self.remove_client(tuple(data['client']))
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
                elif address in self.client_public_keys:
                    # forward update to lb
                    self.handle_and_forward_update(data=data, address=address)
                else:
                    logging.warning(
                        f'address not in clients or lb: {address=}, {self.client_public_keys=}, {self.lb_address=}')
            except Exception:
                logging.exception('exception while handling request')

    def handle_and_forward_update(self, data, address):
        cmd = data['cmd']
        if cmd not in ['move', 'attack', 'projectile', 'disconnect', 'item_dropped', 'item_picked',
                       'use_item', 'use_skill']:
            logging.warning(f'unknown client cmd: {data=}, {address=}')
            return

        player = self.players[data['id']]
        chunk = get_chunk(player.get_pos())
        logging.debug(f'{chunk=}, {data=}')

        # when cmd is move, send update whenever any one of start_pos, end_pos is in a shared chunk
        if chunk in self.shared_chunks or (cmd == 'move' and get_chunk(data['pos']) in self.shared_chunks):
            self.forwarded_updates.append((data, chunk))
        elif cmd == 'disconnect':
            data['player'] = player
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
        for client in self.client_public_keys:
            send_all(self.socket, data, client, self.fernets[self.client_public_keys[client]])

    def backups_sender(self):
        while True:
            time.sleep(BACKUP_DELAY)
            if self.players:
                data = json_encode({'cmd': 'backups', 'players': self.players}, items=True)
                send_all(self.socket, data, self.lb_address, self.lb_fernet)
                logging.info(f'backup sent to db')


def main():
    logging.basicConfig(level=logging.DEBUG)

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
