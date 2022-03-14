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
        self.main_player_id = None

    def send_update(self, cmd: str, params: dict):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode() + b'\n', self.server)

    def create_entity(self, entity: dict):
        e = game.Entity(pos=entity['pos'], sprite_groups=self.all_sprite_groups,
                        animations=self.player_animations,
                        walk_speed=entity['walk_speed'], anim_speed=self.player_anim_speed, id_=entity['id'])
        for item in entity['items']:
            # game.Item(item_type=item['type'], owner=e, id_=item['id'])
            pass

    def get_entity_by_id(self, id_: int):
        entity_sprites, projectile_sprites = self.all_sprite_groups[1:]
        ids = [entity.id for entity in entity_sprites.sprites()]
        return entity_sprites.sprites()[ids.index(id_)]

    def create_projectile(self, projectile: dict):
        attacker = self.get_entity_by_id(projectile['attacker_id'])
        game.Projectile(proj_type=projectile['type'], attacker=attacker, all_sprite_groups=self.all_sprite_groups,
                        vect=pygame.Vector2(projectile['target']), send_update=False)

    def handle_update(self, update: dict):
        entity_sprites, projectile_sprites = self.all_sprite_groups[1:]
        cmd = update['cmd']
        ids = [entity.id for entity in entity_sprites.sprites()]

        if cmd == 'new':
            if update['entity']['id'] not in ids:
                self.create_entity(update['entity'])
        elif cmd == 'projectile' and update['projectile']['attacker_id'] != self.main_player_id:
            self.create_projectile(update['projectile'])
        elif update['id'] != self.main_player_id:
            entity = self.get_entity_by_id(update['id'])

            if cmd == 'move':
                entity.move(*update['pos'], send_update=False)
            elif cmd == 'attack':
                # check collision with mob_ids
                entity.melee_attack(send_update=False)
            elif cmd == 'use_item':
                item_ids = [item.id for item in entity.items.sprites()]
                item = entity.items.sprites()[item_ids.index(update['item_id'])]
                item.use_item(send_update=False)
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
                    elif cmd == 'connect':
                        for entity in data['entities']:
                            self.create_entity(entity)
                        for projectile in data['projectiles']:
                            self.create_projectile(projectile)
                        self.main_player_id = data['id']
                except Exception:
                    logging.exception('exception while handling update')
