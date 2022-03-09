import logging
import queue
import socket
import sys
import threading
import time
from typing import Dict, Sequence, Tuple, Set

from network.player import Player
from network.section_mapping import default_mapping
from settings import *
from network.utils import parse_cmd, serialize_cmd, Address, socket_handler


class SectionServer:
    def __init__(self, external_address: Address, internal_address: Address, section_servers: Sequence[Address],
                 map_size: Tuple[int, int]):
        self.internal_address = internal_address
        self.external_address = external_address

        self.external_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.external_sock.bind(external_address)
        self.internal_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.internal_sock.bind(internal_address)

        self.mapping = default_mapping(servers=section_servers, map_size=map_size)  # internal server addresses
        self.players: Dict[int, Player] = {}

        self.watching_clients: Set[Address] = set()  # clients that receive updates
        self.updates_queue = queue.Queue()

        self.change_player_section_timers: Dict[int, threading.Timer] = {}

        logging.debug(f'section server init: {self.mapping=}')

    def change_player_section(self, player_id: int, internal_address: Address):
        logging.debug(f'player section change event: {player_id=}, {internal_address=}')
        data = serialize_cmd(cmd='add_player', params=self.players[player_id].to_dict())
        self.internal_sock.sendto(data, internal_address)
        del self.players[player_id]
        del self.change_player_section_timers[player_id]

    def handle_movement(self, cmd: str, params: dict, address: Address):
        player = self.players[params['id']]

        if not (0 <= params['target'][0] < self.mapping.map_size[0] and 0 <= params['target'][1] <
                self.mapping.map_size[1]):
            logging.warning(f'player tried to leave the map: {cmd=}, {params=}, {address=}')
            return

        player.move(params['target'], params['t'])
        self.updates_queue.put({'update': cmd, **params})
        logging.debug(f'player moved: target={params["target"]}, t={params["t"]}, '
                      f'section_server={self.mapping.get_server(params["target"])}, {player=}')

        if player.id in self.change_player_section_timers:
            prev_timer = self.change_player_section_timers[player.id]
            prev_timer.cancel()
            logging.debug(f'player section change canceled: {prev_timer=}, {player=}')

        if self.mapping.get_server(player.start_pos) != self.mapping.get_server(player.end_pos):
            this_index = self.mapping.servers.index(self.internal_address)
            if player.end_pos[0] > player.start_pos[0]:
                border_x = self.mapping.sections[this_index + 1]
                next_server = self.mapping.servers[this_index + 1]
            else:
                border_x = self.mapping.sections[this_index]
                next_server = self.mapping.servers[this_index - 1]
            t = player.get_crossing_time(border_x)
            timer = threading.Timer(interval=t - player.t0, function=self.change_player_section,
                                    args=(player.id, next_server))
            timer.start()
            self.change_player_section_timers[player.id] = timer
            logging.debug(f'player section change scheduled: {border_x=}, {next_server=}, {t=}, {player=}')

    def handle_player_action(self, cmd: str, params: dict, address: Address):
        action, player_id, t = params['action'], params['id'], params['t']
        logging.debug(f'new player action: {params=}, {address=}')

        if player_id in self.players:
            time_diff = abs(time.time() - t)
            if time_diff < 2:
                logging.debug(f'time diff is ok: {time_diff=}')
                if action == 'move':
                    self.handle_movement(cmd=cmd, params=params, address=address)
            else:
                logging.warning(f'time diff is too big: {time_diff=}')
        else:
            logging.warning(f'player not in section: {player_id=}')

    def handle_client_request(self, request: bytes, address: Address):
        cmd, params = parse_cmd(request)
        if cmd == 'receive_updates':
            self.watching_clients.add(address)
            logging.debug(f'client added to watching clients: {address=}, {self.watching_clients=}')
        elif cmd == 'stop_receiving_updates':
            self.watching_clients.discard(address)
            logging.debug(f'client removed from watching clients: {address=}, {self.watching_clients=}')
        elif cmd == 'get_section_data':
            data = serialize_cmd(cmd, {'players': {id_: p.to_dict() for id_, p in self.players.items()}})
            self.external_sock.sendto(data, address)
        elif cmd == 'player_action':
            self.handle_player_action(cmd=cmd, params=params, address=address)
        elif cmd != '':
            logging.warning(f'unknown external cmd: {cmd=}, {params=}, {address=}')

    def handle_internal_request(self, request: bytes, address: Address):
        cmd, params = parse_cmd(request)

        if cmd == 'add_player':
            self.players[params['id']] = Player(**params)
            self.updates_queue.put({'update': cmd, **params})
            logging.debug(f'player added: {params=}, {address=}')
        elif cmd == 'remove_player':
            del self.players[params['id']]
            self.updates_queue.put({'update': cmd, **params})
            logging.debug(f'player removed: {params=}')
        elif cmd != '':
            logging.warning(f'unknown internal cmd: {cmd=}, {params=}, {address=}')

    def updates_sender(self):
        """
        Wait for updates and send to watching clients
        """
        while True:
            update = self.updates_queue.get()
            logging.debug(f'sending update: {update=}, {self.watching_clients=}')
            data = serialize_cmd('section_updates', update)
            for watcher in self.watching_clients:
                self.external_sock.sendto(data, watcher)

    def run(self):
        threads = [
            threading.Thread(target=self.updates_sender),
            threading.Thread(target=socket_handler, args=(self.external_sock, 'external', self.handle_client_request)),
            threading.Thread(target=socket_handler,
                             args=(self.internal_sock, 'internal', self.handle_internal_request)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()


def main():
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s:%(thread)d]\t%(message)s')
    server_id = int(sys.argv[1])

    server = SectionServer(external_address=SERVERS_EXTERNAL[server_id], internal_address=SERVERS_INTERNAL[server_id],
                           section_servers=SERVERS_INTERNAL, map_size=MAP_SIZE)
    server.run()


if __name__ == '__main__':
    main()
