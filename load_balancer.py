import logging
from typing import Dict

from my_server import Player, MyJSONEncoder, generate_id
from utils import *


class LoadBalancer:
    def __init__(self, sock: socket.socket, servers):
        self.socket = sock

        self.servers = servers
        self.clients = {}  # id to client address
        self.player_chunks: Dict[int, Tuple[int, int]] = {}  # id to chunk

        self.chunk_mapping = generate_chunk_mapping()

    def get_server(self, chunk_idx: Tuple[int, int]):
        return self.servers[self.chunk_mapping[chunk_idx[0]][chunk_idx[1]]]

    def send_cmd(self, cmd: str, params: dict, address):
        data = json.dumps({'cmd': cmd, **params}, cls=MyJSONEncoder).encode() + b'\n'
        self.socket.sendto(data, address)

    def connect(self, data, client):
        items = {str(generate_id()): "speed_pot"}
        player = Player(id=None, start_pos=(1400, 1360), end_pos=None,
                        health=100, items=items, t0=0, username=data['username'])
        chunk = get_chunk(player.start_pos)
        server = self.get_server(chunk)
        self.clients[player.id] = client
        self.player_chunks[player.id] = chunk
        self.send_cmd('connect', {'player': player, 'client': client}, server)
        self.send_cmd('redirect', {'server': server}, client)
        logging.debug(f'new client connected: {client=}, {player=}, {server=}, {chunk=}')

    def forward_updates(self, data, address):
        updates_by_server_idx = [[] for _ in self.servers]

        for update_idx, chunk_idx in enumerate(data['chunks']):
            update = data['updates'][update_idx]
            # redirect clients
            if update['cmd'] == 'move':
                new_server = self.get_server(get_chunk(update['pos']))
                if new_server != address:
                    client = self.clients[update['id']]
                    logging.debug(f'client changed server: {client=}, {address=}, {new_server=}')
                    self.send_cmd('redirect', {'server': new_server}, client)
                    self.send_cmd('add_client', {'client': client, 'id': update['id']}, new_server)
                    self.send_cmd('remove_client', {'client': client, 'id': update['id']}, address)
                for adj_server_idx in range(len(self.servers)):
                    if adj_server_idx in get_adj_server_idx(self.chunk_mapping, chunk_idx) or \
                            adj_server_idx in get_adj_server_idx(self.chunk_mapping, get_chunk(update['pos'])):
                        updates_by_server_idx[adj_server_idx].append(update_idx)
            # remove client internally
            else:
                if update['cmd'] == 'disconnect':
                    update['cmd'] = 'player_leaves'
                    del self.clients[update['id']]
                for adj_server_idx in get_adj_server_idx(chunk_mapping=self.chunk_mapping, chunk_idx=chunk_idx):
                    updates_by_server_idx[adj_server_idx].append(update_idx)

        for move_data in data['moving_players']:
            start_chunk, end_chunk, player = move_data['start_chunk'], move_data['end_chunk'], move_data['player']
            adj_start = get_adj_server_idx(self.chunk_mapping, start_chunk)
            adj_end = get_adj_server_idx(self.chunk_mapping, end_chunk)
            data['updates'].append({
                'cmd': 'player_enters', 'player': player
            })
            data['updates'].append({
                'cmd': 'player_leaves', 'id': player['id']
            })
            for server_idx in adj_end:
                if server_idx not in adj_start:
                    # player enters server
                    updates_by_server_idx[server_idx].insert(0, len(data['updates']) - 2)
            for server_idx in adj_start:
                if server_idx not in adj_end:
                    # player leaves server
                    updates_by_server_idx[server_idx].append(len(data['updates']) - 1)

        logging.debug(f'sent updates: {updates_by_server_idx=}')
        for i, updates_idx in enumerate(updates_by_server_idx):
            server = self.servers[i]
            if updates_idx:
                self.send_cmd('update', {'updates': [data['updates'][update] for update in updates_idx]}, server)

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(1024)
                data = json.loads(msg)
                logging.debug(f'received data: {data=}')

                if data["cmd"] == "connect":
                    if address not in self.servers:
                        self.connect(data=data, client=address)
                elif data['cmd'] == 'forward_updates':
                    if address in self.servers:
                        self.forward_updates(data, address)
            except Exception:
                logging.exception('exception while handling request')


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(LB_ADDRESS)

    lb = LoadBalancer(servers=SERVER_ADDRESSES, sock=sock)
    # for row in lb.chunk_mapping:
    #     print(row)

    lb.receive_packets()


if __name__ == '__main__':
    main()
