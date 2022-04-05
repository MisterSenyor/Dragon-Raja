import logging
import sys

from my_server import *
from settings import *


class NewServer(Server):
    def __init__(self, sock: socket.socket, lb_address, server_chunks: List[Tuple[int, int]],
                 shared_chunks: List[Tuple[int, int]]):
        super(NewServer, self).__init__(sock=sock)
        self.lb_address = lb_address

        self.server_chunks = server_chunks
        self.shared_chunks = shared_chunks
        self.private_chunks = [chunk for chunk in self.server_chunks if chunk not in self.shared_chunks]

        logging.debug(f'{self.private_chunks=}')

        self.forwarded_updates = []

    def generate_mobs(self, count):
        for _ in range(count):
            chunk = random.choice(self.private_chunks)
            pos_x = chunk[0] * CHUNK_SIZE + random.randint(0, CHUNK_SIZE - 1)
            pos_y = chunk[1] * CHUNK_SIZE + random.randint(0, CHUNK_SIZE - 1)
            m = Mob(id=None,
                    start_pos=(pos_x, pos_y),
                    end_pos=None,
                    health=100, t0=0)
            self.mobs[m.id] = m

    def mob_move(self, mob: Mob):
        pos = mob.get_pos()
        new_pos = pos[0] + random.randint(-500, 500), pos[1] + random.randint(-500, 500)
        while get_chunk(new_pos) not in self.private_chunks:
            new_pos = pos[0] + random.randint(-500, 500), pos[1] + random.randint(-500, 500)
        mob.move(pos=new_pos)
        # logging.debug(f'mob moved: {mob=}')
        self.updates.append({'cmd': 'move', 'pos': mob.end_pos, 'id': mob.id})

    def add_client(self, player, client, init):
        client = tuple(client)
        if init:
            data = {
                'cmd': 'init',
                'main_player': player,
                'players': list(self.players.values()),
                'mobs': list(self.mobs.values()),
                'projectiles': list(self.projectiles.values()),
                'dropped': list(self.dropped.values())
            }
        else:
            data = {
                'cmd': 'get_data',
                'players': list(self.players.values()),
                'mobs': list(self.mobs.values()),
                'dropped': list(self.dropped.values())
            }
        state = json.dumps(data, cls=MyJSONEncoder).encode() + b'\n'
        send_all(self.socket, state, client)
        self.clients.append(client)
        logging.debug(f'new client connected: {client=}, {player=}')

    def connect(self, data, address):
        player = Player(**data['player'], t0=time.time_ns(), items={})
        self.updates.append({'cmd': 'player_enters', 'player': player})
        self.add_client(player, data['client'], init=True)
        self.players[player.id] = player

    def add_player(self, data):
        if data['player']['id'] not in self.players:
            player = Player(**data['player'], t0=time.time_ns(), items={})
            self.players[player.id] = player

    def remove_player(self, data):
        if data['id'] in self.players:
            del self.players[data['id']]

    def handle_update(self, data, address):
        cmd = data['cmd']
        if cmd == 'player_enters':
            self.add_player(data)
        elif cmd == 'player_leaves':
            self.remove_player(data)
        else:
            super(NewServer, self).handle_update(data=data, address=address)

    def handle_lb_update(self, data, address):
        cmd = data['cmd']
        if cmd == "connect":
            self.connect(data=data, address=address)
        elif cmd == 'add_client':
            self.add_client(self.players[data['id']], data['client'], init=False)
        elif cmd == 'remove_client':
            if tuple(data['client']) in self.clients:
                self.clients.remove(tuple(data['client']))
        elif cmd == 'update':
            # send updates to clients
            for update in data['updates']:
                self.handle_update(data=update, address=address)

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(settings.HEADER_SIZE)
                data = json.loads(msg.decode())
                logging.debug(f'received data: {data=}, {address=}')

                if address == self.lb_address:
                    self.handle_lb_update(data=data, address=address)
                elif address in self.clients:
                    # forward update to lb
                    self.handle_client_update(data=data, address=address)
                else:
                    logging.warning(f'address not in clients or lb: {address=}, {self.clients=}, {self.lb_address=}')
            except Exception:
                logging.exception('exception while handling request')

    def handle_client_update(self, data, address):
        cmd = data['cmd']
        if cmd in ['move', 'attack', 'projectile', 'disconnect', 'item_dropped', 'item_picked']:
            player = self.players[data['id']]
        chunk = get_chunk(player.get_pos())
        logging.debug(f'{chunk=}, {data=}')

        # when cmd is move, send update whenever any one of start_pos, end_pos is in a shared chunk
        if chunk in self.shared_chunks or (cmd == 'move' and get_chunk(data['pos']) in self.shared_chunks):
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
            data = json.dumps({'cmd': 'forward_updates', 'updates': updates, 'chunks': chunks,
                               'moving_players': moving_players}, cls=MyJSONEncoder).encode() + b'\n'
            send_all(self.socket, data, self.lb_address)
            logging.debug(f'updates sent to lb: {updates=}, {chunks=}')
        self.forwarded_updates.clear()


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
    server.generate_mobs(20)
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        # server.collisions_handler()
        server.send_updates()
        server.update_mobs()
        server.forward_updates()


if __name__ == '__main__':
    main()
