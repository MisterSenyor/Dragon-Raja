import base64
import json
import logging
import socket
from collections import defaultdict
from typing import Tuple, Collection, Any, Dict

import cryptography.fernet
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from settings import *

CURVE = ec.SECP384R1()
Address = Tuple[str, int]


class UnknownClientException(Exception):
    pass


def send_all(sock: socket.socket, data: bytes, address, fernet):
    try:
        k = 0
        data = fernet.encrypt(data)
        while k * 1024 < len(data):
            sock.sendto(data[1024 * k: 1024 * (k + 1)], address)
            k += 1
    except Exception:
        logging.exception(f"can't send data: {address=}, {data=}")


class JSONSocketWrapper:
    def __init__(self, sock: socket.socket, fernet, max_iterations=10):
        self.socket = sock
        self.max_iterations = max_iterations
        self.received: Dict[Any, list] = defaultdict(lambda: [0, b''])
        self.fernet = fernet

    def recv_from(self):
        while True:
            msg, addr = self.socket.recvfrom(1024)
            self.received[addr][1] += msg
            self.received[addr][0] += 1
            try:
                data = self.fernet.decrypt(self.received[addr][1])
                json_data = json.loads(data.decode())
                # logging.debug(f'received data: {k=}, {len(data)=}, {data=}')
                del self.received[addr]
                return json_data, addr
            except (json.JSONDecodeError, cryptography.fernet.InvalidToken):
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


def ascii_seed(seed):
    ascii_sum = 0
    for char in seed:
        ascii_sum += ord(char)
    return ascii_sum


def encrypt_packet(data):
    return data


def decrypt_packet(data):
    return data


def serialize_public_key(key):
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


def serialize_private_key(key):
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )


def generate_ecdh_key():
    with open('private.PEM', 'wb') as file:
        private_key = ec.generate_private_key(
            CURVE
        )
        serialized_private = serialize_private_key(private_key)
        file.write(serialized_private)
    with open('public.PEM', 'wb') as file:
        public_key = private_key.public_key()
        serialized_public = serialize_public_key(public_key)
        file.write(serialized_public)
    return private_key


def load_public_ecdh_key():
    with open('public.PEM', 'rb') as file:
        loaded_public_key = serialization.load_pem_public_key(
            file.read(),
        )
        return loaded_public_key


def load_private_ecdh_key():
    with open('private.PEM', 'rb') as file:
        loaded_private_key = serialization.load_pem_private_key(
            file.read(),
            # or password=None, if in plain text
            password=None,
        )
        return loaded_private_key


def get_pk_and_data(msg: bytes) -> Tuple[bytes, bytes]:
    print(msg)
    end = b'-----END PUBLIC KEY-----\n'
    pk, data = msg.split(end)
    return pk + end, data


def get_fernet(public_key, private_key):
    shared_key = private_key.exchange(ec.ECDH(), public_key)
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'handshake data',
    ).derive(shared_key)
    derived_key = base64.urlsafe_b64encode(derived_key)
    return Fernet(derived_key)


def client():
    # generate_ecdh_key()
    server_public_key = load_public_ecdh_key()
    client_private_key = ec.generate_private_key(CURVE)
    fernet = get_fernet(server_public_key, client_private_key)
    serialized_client_public_key = serialize_public_key(client_private_key.public_key())

    encrypted = server(serialized_client_public_key)
    print(fernet.decrypt(encrypted))


def server(serialized_client_public_key):
    server_private_key = load_private_ecdh_key()
    client_public_key = serialization.load_pem_public_key(serialized_client_public_key)
    fernet = get_fernet(client_public_key, server_private_key)
    return fernet.encrypt(b'123')
