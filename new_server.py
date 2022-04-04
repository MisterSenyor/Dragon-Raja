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

        self.mobs = {}
        self.forwarded_updates = []

    def connect(self, data, address):
        player = Player(**data['player'], t0=time.time_ns(), items={})
        self.updates.append({'cmd': 'player_enters', 'player': player})

        state = json.dumps({
            'cmd': 'init',
            'main_player': player,
            'players': list(self.players.values()),
            'mobs': list(self.mobs.values()),
            'projectiles': list(self.projectiles.values()),
            'dropped': list(self.dropped.values())
        }, cls=MyJSONEncoder).encode() + b'\n'
        client = tuple(data['client'])
        send_all(self.socket, state, client)

        self.clients.append(client)
        self.players[player.id] = player

        logging.debug(f'new client connected: {client=}, {player=}')

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

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(settings.HEADER_SIZE)
                data = json.loads(msg.decode())
                logging.debug(f'received data: {data=}, {address=}')

                cmd = data['cmd']
                if address == self.lb_address:
                    if cmd == "connect":
                        self.connect(data=data, address=address)
                    elif cmd == 'add_client':
                        self.clients.append(tuple(data['client']))
                    elif cmd == 'remove_client':
                        if tuple(data['client']) in self.clients:
                            self.clients.remove(tuple(data['client']))
                    elif cmd == 'update':
                        # send updates to clients
                        for update in data['updates']:
                            self.handle_update(data=update, address=address)
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
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        # server.collisions_handler()
        server.send_updates()
        server.forward_updates()


if __name__ == '__main__':
    main()
