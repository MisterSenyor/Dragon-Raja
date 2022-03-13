import json
import logging
from typing import Sequence

import pygame

import game
from network.utils import Address
from settings import *


class Client:
    def __init__(self, sock: socket.socket, server: Address, all_sprite_groups: Sequence[pygame.sprite.Group],
                 player_animations, player_anim_speed):
        self.sock = sock
        self.server = server
        self.all_sprite_groups = all_sprite_groups
        self.player_animations = player_animations
        self.player_anim_speed = player_anim_speed

    def send_update(self, cmd: str, params: dict):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode(), self.server)

    def handle_update(self, update: dict):
        entity_sprites, projectile_sprites = self.all_sprite_groups[1:]
        cmd = update['cmd']

        if cmd == 'new':
            entity = update['entity']
            e = game.Entity(pos=entity['pos'], sprite_groups=self.all_sprite_groups, animations=self.player_animations,
                            walk_speed=entity['walk_speed'], anim_speed=self.player_anim_speed, id_=entity['id'])
            for item in entity['items']:
                game.Item(item_type=item['type'], owner=e, id_=item['id'])
        else:
            ids = [entity.id for entity in entity_sprites.sprites()]
            entity = entity_sprites.sprites()[ids.index(update['id'])]

            if cmd == 'move':
                entity.move(*update['pos'])
            elif cmd == 'attack':
                # check collision with mob_ids
                entity.melee_attack()
            elif cmd == 'projectile':
                projectile = update['projectile']
                game.Projectile(proj_type=projectile['type'], attacker=entity, all_sprite_groups=self.all_sprite_groups,
                                vect=pygame.Vector2(projectile['target']))
            elif cmd == 'use_item':
                item_ids = [item.id for item in entity.items.sprites()]
                item = entity.items.sprites()[item_ids.index(update['item_id'])]
                item.use_item()
            elif cmd == 'disconnect':
                entity.kill()

    def receive_updates(self):
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
                            self.handle_update(update)
                except Exception:
                    logging.exception('exception while handling update')
