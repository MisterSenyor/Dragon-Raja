import json
import logging
import socket
from typing import Tuple, Collection, Any, Dict
from collections import defaultdict

from settings import *


def send_all(sock: socket.socket, data: bytes, address):
    try:
        k = 0
        while k * 1024 < len(data):
            sock.sendto(data[1024 * k: 1024 * (k + 1)], address)
            k += 1
    except Exception:
        logging.exception(f"can't send data: {address=}, {data=}")


class JSONSocketWrapper:
    def __init__(self, sock: socket.socket, max_iterations=10):
        self.socket = sock
        self.max_iterations = max_iterations
        self.received: Dict[Any, list] = defaultdict(lambda: [0, b''])

    def recv_from(self):
        while True:
            msg, addr = self.socket.recvfrom(1024)
            self.received[addr][1] += msg
            self.received[addr][0] += 1
            try:
                json_data = json.loads(self.received[addr][1])
                # logging.debug(f'received data: {k=}, {len(data)=}, {data=}')
                del self.received[addr]
                return json_data, addr
            except json.JSONDecodeError:
                if self.received[0] == self.max_iterations:
                    logging.warning(f'max iterations exceeded in recv_json')
                    del self.received[addr]


def dist(pos1, pos2):
    return ((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2) ** 0.5


def get_chunk(pos: Tuple[int, int]) -> Tuple[int, int]:
    return pos[0] // CHUNK_SIZE, pos[1] // CHUNK_SIZE


def generate_chunk_mapping():
    chunk_mapping = []
    mid_x = CHUNKS_X // 2
    mid_y = CHUNKS_Y // 2
    for i in range(CHUNKS_X):
        chunk_mapping.append([])
        for j in range(CHUNKS_Y):
            chunk_mapping[i].append(2 * (i <= mid_x) + (j <= mid_y))  # magic
    return chunk_mapping


def get_adj_server_idx(chunk_mapping, chunk_idx: Tuple[int, int]) -> Collection:
    i, j = chunk_idx
    servers = set()
    for di in [-1, 0, 1]:
        for dj in [-1, 0, 1]:
            if 0 <= i + di < CHUNKS_X and 0 <= j + dj < CHUNKS_Y:
                servers.add(chunk_mapping[i + di][j + dj])
    return servers
