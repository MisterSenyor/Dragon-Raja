from typing import Dict

import pygame

import entities
from network.utils import Address
from utils import *


def create_entity(cls, data, sprite_groups, walk_speed, animations, anim_speed, **kwargs):
    entity = cls(
        pos=data['start_pos'], sprite_groups=sprite_groups, animations=animations, walk_speed=walk_speed,
        anim_speed=anim_speed, id_=data['id'], **kwargs)
    entity.health = data['health']
    entity.move(*data['end_pos'], send_update=False)
    for item in data['items']:
        entity.Item(item_type=item['item_type'], owner=entity)
    return entity


class Client:
    def __init__(self, sock: socket.socket, server: Address, sprite_groups: Dict[str, pygame.sprite.Group],
                 player_animations, player_anim_speed, mob_animations, mob_anim_speed, player_walk_speed,
                 mob_walk_speed):
        self.sock = sock
        self.server = server
        self.sprite_groups = sprite_groups

        self.player_animations = player_animations
        self.player_anim_speed = player_anim_speed
        self.mob_animations = mob_animations
        self.mob_anim_speed = mob_anim_speed

        self.player_walk_speed = player_walk_speed
        self.mob_walk_speed = mob_walk_speed

        self.main_player = None

        self.entity_sprite_groups = [self.sprite_groups['all'], self.sprite_groups['entity']]
        self.projectile_sprite_groups = [self.sprite_groups['all'], self.sprite_groups['projectiles']]
        self.player_sprite_groups = self.entity_sprite_groups + [self.sprite_groups['players']]
        self.dropped_sprite_groups = [self.sprite_groups['all'], self.sprite_groups['dropped']]

    def send_update(self, cmd: str, params: dict):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode() + b'\n', self.server)

    def create_main_player(self, data):
        return create_entity(cls=entities.MainPlayer, data=data, sprite_groups=self.player_sprite_groups,
                             walk_speed=self.player_walk_speed, sock_client=self,
                             animations=self.player_animations, anim_speed=self.player_anim_speed)

    def create_player(self, data):
        return create_entity(cls=entities.Player, data=data, sprite_groups=self.player_sprite_groups,
                             walk_speed=self.player_walk_speed, animations=self.player_animations,
                             anim_speed=self.player_anim_speed)

    def create_mob(self, data):
        return create_entity(cls=entities.Entity, data=data, sprite_groups=self.entity_sprite_groups,
                             walk_speed=self.mob_walk_speed, anim_speed=self.mob_anim_speed,
                             animations=self.mob_animations)

    def create_projectile(self, data):
        entities.Projectile(proj_type=data['type'], attacker=self.get_entity_by_id(data['attacker_id']),
                            sprite_groups=self.projectile_sprite_groups, vect=pygame.Vector2(data['target']),
                            send_update=False)

    def create_dropped(self, data):
        entities.Dropped(item_type=data['item_type'], pos=data['pos'], sprite_groups=self.dropped_sprite_groups)

    def init(self, username='ariel'):
        self.send_update('connect', {'username': username})
        data = recv_json(self.sock, self.server)
        logging.debug(f'init data received: {data=}')
        try:
            if data['cmd'] == 'init':
                self.main_player = self.create_main_player(data['main_player'])
                for player_data in data['players']:
                    self.create_player(player_data)
                for mob_data in data['mobs']:
                    self.create_mob(mob_data)
                for projectile_data in data['projectiles']:
                    self.create_projectile(projectile_data)
        except Exception:
            logging.exception(f'exception in init')

    def get_entity_by_id(self, id_: int):
        entities = self.sprite_groups['entity'].sprites()
        ids = [entity.id for entity in entities]
        return entities[ids.index(id_)]

    def handle_update(self, update: dict):
        cmd = update['cmd']
        player_ids = [player.id for player in self.sprite_groups['players'].sprites()]
        if cmd == 'player_enters':
            if update['player']['id'] not in player_ids:
                self.create_player(update['player'])
        elif cmd == 'projectile' and update['id'] != self.main_player.id:
            self.create_projectile(update['projectile'])
        elif cmd == 'collisions':
            pass
        elif cmd == 'item_dropped':
            self.create_dropped(update['item'])

        elif update['id'] != self.main_player.id:
            entity = self.get_entity_by_id(update['id'])

            if cmd == 'move':
                entity.move(*update['pos'], send_update=False)
            elif cmd == 'attack':
                # check collision with mob_ids
                entity.melee_attack(send_update=False)
            elif cmd == 'use_item':
                item = entities.Item(item_type=update['item_type'], owner=entity)
                item.use_item(send_update=False)
            elif cmd == 'player_leaves':
                entity.kill()


    def receive_updates(self):
        while True:
            data = recv_json(self.sock, self.server)
            try:
                cmd = data['cmd']
                if cmd == 'update':
                    updates = data['updates']
                    if updates:
                        logging.debug(f'received updates: {updates=}')
                    for update in updates:
                        self.handle_update(update)
            except Exception:
                logging.exception(f'exception while handling update: {data=}')
