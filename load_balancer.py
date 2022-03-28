import logging
from typing import Tuple, Collection

from my_server import Player, MyJSONEncoder
from settings import *
from utils import *


class LoadBalancer:
    def __init__(self, sock: socket.socket, servers, map_size: Tuple[int, int], chunk_size: int):
        self.socket = sock

        self.servers = servers
        self.map_size = map_size
        self.chunk_size = chunk_size

        self.chunks_x = self.map_size[0] // self.chunk_size
        self.chunks_y = self.map_size[1] // self.chunk_size
        self.chunk_mapping = None
        self.generate_chunk_mapping()

    def generate_chunk_mapping(self):
        self.chunk_mapping = []
        mid_x = self.chunks_x // 2
        mid_y = self.chunks_y // 2
        for i in range(self.chunks_x):
            self.chunk_mapping.append([])
            for j in range(self.chunks_y):
                self.chunk_mapping[i].append(2 * (i <= mid_x) + (j <= mid_y))  # magic

    def get_chunk(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        return pos[0] // self.chunk_size, pos[1] // self.chunk_size

    def get_server(self, chunk_idx: Tuple[int, int]):
        return self.servers[self.chunk_mapping[chunk_idx[0]][chunk_idx[1]]]

    def get_adj_server_idx(self, chunk_idx: Tuple[int, int]) -> Collection:
        i, j = chunk_idx
        servers = set()
        for di in [-1, 0, 1]:
            for dj in [-1, 0, 1]:
                if 0 <= i + di <= self.chunks_x and 0 <= j + dj < self.chunks_y:
                    servers.add(self.chunk_mapping[i + di][j + dj])
        return servers

    def send_cmd(self, cmd: str, params: dict, address):
        data = json.dumps({'cmd': cmd, **params}, cls=MyJSONEncoder).encode() + b'\n'
        self.socket.sendto(data, address)

    def connect(self, data, client):
        player = Player(id=None, start_pos=(1400, 1360), end_pos=None,
                        health=100, items=[], t0=0, username=data['username'])
        server = self.get_server(player.start_pos)
        self.send_cmd('connect', {'player': player, 'client': client}, server)
        self.send_cmd('redirect', {'server': server}, client)
        logging.debug(f'new client connected: {client=}, {player=}, {server=}')

    def forward_updates(self, data, address):
        updates_by_server_idx = [[] for _ in self.servers]
        for chunk in data['chunks']:
            chunk_idx = chunk['chunk_idx']
            for adj_server in self.get_adj_server_idx(chunk_idx):
                if adj_server != address:
                    updates_by_server_idx[adj_server].extend(chunk['update_indices'])
        logging.debug(f'{updates_by_server_idx=}, {address=}')
        for i, updates_idx in enumerate(updates_by_server_idx):
            server = self.servers[i]
            if updates_idx:
                self.send_cmd('update', {'updates': [data['updates'][update] for update in updates_idx]}, server)

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(1024)
                data = json.loads(msg.decode())
                logging.debug(f'received data: {data=}')

                if data["cmd"] == "connect":
                    if address not in self.servers:
                        self.connect(data=data, client=address)
                elif data['cmd'] == 'forward_updates':
                    if address in self.servers or True:  # TODO: remove
                        self.forward_updates(data, address)
            except Exception:
                logging.exception('exception while handling request')


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(LB_ADDRESS)

    servers = [('127.0.0.1', p) for p in [11110, 11111, 11112, 11113]]
    lb = LoadBalancer(servers=servers, map_size=MAP_SIZE, chunk_size=CHUNK_SIZE, sock=sock)
    # for row in lb.chunk_mapping:
    #     print(row)

    lb.receive_packets()


if __name__ == '__main__':
    main()
