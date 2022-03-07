import json
import logging
import socket
from typing import Tuple, Callable

Address = Tuple[str, int]


def distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
    """
    Compute the euclidean distance between two points
    :param p1: first point
    :param p2: second point
    :return: the distance
    """
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def serialize_cmd(cmd: str, params: dict) -> bytes:
    """
    Convert a cmd and params to a stream of bytes
    :param cmd: message cmd
    :param params: message params
    :return: message in bytes
    """
    cmd = cmd.replace(' ', '_')
    data = cmd + ' ' + json.dumps(params) + '\n'
    return data.encode()


def parse_cmd(data: bytes) -> Tuple[str, dict]:
    """
    Parse cmd and params from a given message
    :param data: the message to parse
    :return: a tuple (cmd, params) parsed from the data
    """
    try:
        cmd, json_data = data.decode().split(maxsplit=1)
        return cmd, json.loads(json_data)
    except Exception:
        logging.exception(f'exception while parsing cmd: {data}')
        return '', {}


def socket_handler(sock: socket.socket, name: str, request_handler: Callable[[bytes, Address], None],
                   verbose: bool = True):
    """
    A function for socket requests handling which ignores exceptions and runs forever
    :param sock: an open udp socket
    :param name: the name of the handler, used for logging
    :param request_handler: handler that receives a tuple (data, address) and called on every reqeust
    :param verbose: whether to log exceptions
    """
    if verbose:
        logging.debug(f'{name} handler listening: {sock.getsockname()=}')
    with sock:
        while True:
            try:
                msg, address = sock.recvfrom(1024)
                request_handler(msg, address)
            except Exception:
                if verbose:
                    logging.exception(f'exception while handling {name} request')
