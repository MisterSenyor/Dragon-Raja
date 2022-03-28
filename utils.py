import socket
import logging
import json


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
            assert addr == address  # wayyy more complex otherwise
            data += msg
            try:
                json_data = json.loads(data)
                # logging.debug(f'received data: {k=}, {len(data)=}, {data=}')
                return json_data
            except json.JSONDecodeError:
                k += 1
            if k == max_iterations:
                raise ConnectionError(f'max iterations exceeded in recv_json')
    except Exception:
        logging.exception(f"can't receive json data: {address=}, {max_iterations=}, {k=}, {data=}")
