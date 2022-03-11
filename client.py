import json

import game
from network.utils import Address
from settings import *


class Client:
    def __init__(self, sock: socket.socket, server: Address):
        self.sock = sock
        self.server = server

    def send_update(self, cmd: str, params: dict):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode(), self.server)

    def handle_update(self, update: dict, all_sprite_groups):
        entity_sprites, projectile_sprites = all_sprite_groups[1:]
        cmd = update['cmd']
        for entity in entity_sprites.sprites():
            if entity.id == update['id']:
                break

        if cmd == 'move':
            entity.move(*update['pos'])
        elif cmd == 'attack':
            # check collision with mob_ids
            entity.melee_attack()
        elif cmd == 'projectile':
            game.Projectile(proj_type=update['type'], attacker=entity, all_sprite_groups=all_sprite_groups,
                            vect=update['target'])

    def receive_updates(self, all_sprite_groups):
        while True:
            msg, address = self.sock.recvfrom(1024)
            print(msg, address)
            if address == self.server or True:
                try:
                    data = json.loads(msg.decode())
                    cmd = data['cmd']
                    if cmd == 'update':
                        updates = data['updates']
                        for update in updates:
                            self.handle_update(update, all_sprite_groups)
                except Exception:
                    continue


def main():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address, data = join(my_socket)
    print(data)


def join(server: socket):
    # Function that handles the client joining the server through the load balancer. Recives socket, returns server address ("IP",PORT) of server and data.
    server.sendto(build_header().zfill(HEADER_SIZE).encode(), (IP, PORT))
    data, server_address = server.recvfrom(HEADER_SIZE)
    data.decode()
    return server_address, data


def build_header():
    return 'hello  world'


if __name__ == '__main__':
    main()
