import json
from typing import Dict

import pygame

from entities import *
from network.utils import Address


class Client:
    def __init__(self, sock: socket.socket, server: Address, sprite_groups: Dict[str, pygame.sprite.Group],
                 player_animations, player_anim_speed, player_walk_speed):
        self.sock = sock
        self.server = server
        self.sprite_groups = sprite_groups

        self.player_animations = player_animations
        self.player_anim_speed = player_anim_speed
        self.player_walk_speed = player_walk_speed

        self.main_player: MainPlayer = None

        self.entity_sprite_groups = [self.sprite_groups['all'], self.sprite_groups['entity']]
        self.projectile_sprite_groups = [self.sprite_groups['all'], self.sprite_groups['projectiles']]
        self.player_sprite_groups = self.entity_sprite_groups + [self.sprite_groups['players']]

    def send_update(self, cmd: str, params: dict):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode() + b'\n', self.server)

    def create_entity(self, cls, data, sprite_groups, walk_speed, **kwargs):
        entity = cls(
            pos=data['start_pos'], sprite_groups=sprite_groups,
            animations=self.player_animations, walk_speed=walk_speed,
            anim_speed=self.player_anim_speed, id_=data['id'], **kwargs)
        entity.health = data['health']
        entity.move(*data['end_pos'], send_update=False)
        # update _t according to data['t0']
        for item in data['items']:
            Item(item_type=item['item_type'], owner=entity)
            # update duration according to data['t0']
        return entity

    def create_main_player(self, data):
        return self.create_entity(cls=MainPlayer, data=data, sprite_groups=self.player_sprite_groups,
                                  walk_speed=self.player_walk_speed, sock_client=self)

    def create_player(self, data):
        return self.create_entity(cls=Player, data=data, sprite_groups=self.player_sprite_groups,
                                  walk_speed=self.player_walk_speed)

    def create_projectile(self, data):
        Projectile(proj_type=data['type'], attacker=self.get_player_by_id(data['attacker_id']),
                   sprite_groups=self.projectile_sprite_groups, vect=pygame.Vector2(data['target']), send_update=False)

    def init(self):
        self.send_update('connect', {'username': 'ariel'})
        while True:
            msg, address = self.sock.recvfrom(1024)
            if address == self.server:
                break
            logging.debug(f'init data received not from server: {address=}, {self.server=}')
        try:
            data = json.loads(msg)
            logging.debug(f'init data received: {data=}')
            if data['cmd'] == 'init':
                self.main_player = self.create_main_player(data['main_player'])
                for player_data in data['players']:
                    self.create_player(player_data)
                for projectile_data in data['projectiles']:
                    self.create_projectile(projectile_data)
        except Exception:
            logging.exception(f'exception in init')

    def get_player_by_id(self, id_: int) -> Player:
        players = self.sprite_groups['players'].sprites()
        ids = [player.id for player in players]
        return players[ids.index(id_)]

    def handle_update(self, update: dict):
        cmd = update['cmd']
        player_ids = [player.id for player in self.sprite_groups['players'].sprites()]

        if cmd == 'player_enters':
            if update['player']['id'] not in player_ids:
                self.create_player(update['player'])
        elif cmd == 'projectile' and update['id'] != self.main_player.id:
            self.create_projectile(update['projectile'])
        elif update['id'] != self.main_player.id:
            player = self.get_player_by_id(update['id'])

            if cmd == 'move':
                player.move(*update['pos'], send_update=False)
            elif cmd == 'attack':
                # check collision with mob_ids
                player.melee_attack(send_update=False)
            elif cmd == 'use_item':
                item = Item(item_type=update['item_type'], owner=player)
                item.use_item(send_update=False)
            elif cmd == 'player_leaves':
                player.kill()

    def receive_updates(self):
        while True:
            msg, address = self.sock.recvfrom(1024)
            if address == self.server:
                try:
                    data = json.loads(msg.decode())
                    cmd = data['cmd']
                    if cmd == 'update':
                        updates = data['updates']
                        if updates:
                            logging.debug(f'received updates: {updates=}')
                        for update in updates:
                            self.handle_update(update)
                except Exception:
                    logging.exception(f'exception while handling update: {msg=}, {address=}')
