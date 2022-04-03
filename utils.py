import json
import logging
import socket
from typing import Tuple, Collection

from settings import *


def send_all(sock: socket.socket, data: bytes, address):
    try:
        k = 0
        while k * 1024 < len(data):
            sock.sendto(data[1024 * k: 1024 * (k + 1)], address)
            k += 1
    except Exception:
        logging.exception(f"can't send data: {address=}, {data=}")


def recv_json(sock: socket.socket, address, max_iterations=10):
    k = 0
    data = b''
    try:
        while True:
            msg, addr = sock.recvfrom(1024)
            # assert addr == address  # wayyy more complex otherwise
            data += msg
            try:
                json_data = json.loads(data)
                # logging.debug(f'received data: {k=}, {len(data)=}, {data=}')
                if address is None:
                    return json_data, addr
                return json_data
            except json.JSONDecodeError:
                k += 1
            if k == max_iterations:
                raise ConnectionError(f'max iterations exceeded in recv_json')
    except Exception:
        logging.exception(f"can't receive json data, {max_iterations=}, {k=}, {data=}")


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
