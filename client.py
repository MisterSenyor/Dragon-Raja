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
    for item_id, item_type in data.pop('items', {}).items():
        entities.Item(item_type=item_type, owner=entity, item_id=item_id)
    return entity


class Client:
    def __init__(self, sock: socket.socket, server: Address, sprite_groups: Dict[str, pygame.sprite.Group],
                 player_animations, player_anim_speed, mob_animations, mob_anim_speed, player_walk_speed,
                 mob_walk_speed):
        self.sock = sock
        self.sock_wrapper = JSONSocketWrapper(self.sock)
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
        self.sock.sendto(decrypt_packet(json.dumps({'cmd': cmd, **params}).encode() + b'\n'), self.server)

    def create_main_player(self, data):
        return self.create_player(data, cls=entities.MainPlayer, sock_client=self)

    def create_player(self, data, cls=entities.Player, **kwargs):
        entity = create_entity(cls=cls, data=data, sprite_groups=self.player_sprite_groups,
                               walk_speed=self.player_walk_speed, animations=self.player_animations,
                               anim_speed=self.player_anim_speed, **kwargs)
        if ENABLE_SHADOWS:
            shadow = create_entity(cls=entities.Player, data=data, sprite_groups=self.player_sprite_groups,
                                   walk_speed=self.player_walk_speed, animations=self.player_animations,
                                   anim_speed=self.player_anim_speed)
            shadow.id += 1
            shadow.kill()
            shadow.add(self.sprite_groups['all'], self.sprite_groups['shadows'])
        return entity

    def create_mob(self, data):
        return create_entity(cls=entities.Entity, data=data, sprite_groups=self.entity_sprite_groups,
                             walk_speed=self.mob_walk_speed, anim_speed=self.mob_anim_speed,
                             animations=self.mob_animations[data['type']])

    def create_projectile(self, data):
        entities.Projectile(proj_type=data['type'], attacker=self.get_entity_by_id(data['attacker_id']),
                            sprite_groups=self.projectile_sprite_groups, vect=pygame.Vector2(data['target']),
                            send_update=False)

    def create_dropped(self, data):
        entities.Dropped(item_type=data['item_type'], pos=data['pos'], sprite_groups=self.dropped_sprite_groups,
                         item_id=data['item_id'])

    def connect(self, username='ariel'):
        self.send_update('connect', {'username': username})
        data, address = self.sock_wrapper.recv_from()
        assert address == self.server
        logging.debug(f'init data received: {data=}')
        self.init(data)

    def init(self, data):
        try:
            assert data['cmd'] == 'init'
            self.main_player = self.create_main_player(data['main_player'])
            for player_data in data['players']:
                self.create_player(player_data)
            for mob_data in data['mobs']:
                self.create_mob(mob_data)
            for projectile_data in data['projectiles']:
                self.create_projectile(projectile_data)
            for dropped_data in data['dropped']:
                self.create_dropped(dropped_data)
        except Exception:
            logging.exception(f'exception in init')

    def get_entity_by_id(self, id_: int):
        sprites = self.sprite_groups['entity'].sprites()
        ids = [sprite.id for sprite in sprites]
        return sprites[ids.index(id_)]

    def get_dropped_by_id(self, id_: int):
        sprites = self.sprite_groups['dropped'].sprites()
        ids = [sprite.item_id for sprite in sprites]
        return sprites[ids.index(id_)]

    def get_shadow_by_id(self, id_: int):
        sprites = self.sprite_groups['shadows'].sprites()
        ids = [sprite.id for sprite in sprites]
        return sprites[ids.index(id_)]

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
            self.create_dropped(update)
        elif cmd == 'item_picked':
            dropped = self.get_dropped_by_id(update['item_id'])
            dropped.kill()
        elif cmd == 'use_item':
            entity = self.get_entity_by_id(update['id'])
            item = entities.Item(item_type=update['item_type'], owner=entity)
            item.use_item(send_update=False)
        elif cmd == 'entity_died':
            # entity = self.get_entity_by_id(update['id'])
            # entity.kill()
            for drop_data in update['drops']:
                self.create_dropped(drop_data)
        elif cmd == 'use_skill':
            entity = self.get_entity_by_id(update['id'])
            entity.use_skill(skill_id=update['skill_id'], sprite_groups=self.sprite_groups, inv=None,
                             send_update=False)
        elif ENABLE_SHADOWS and cmd == 'shadows':
            for player in update['players']:
                shadow = self.get_shadow_by_id(player['id'] + 1)
                shadow.rect.center = player['pos']
        elif update['id'] != self.main_player.id:
            entity = self.get_entity_by_id(update['id'])

            if cmd == 'move':
                entity.move(*update['pos'], send_update=False)
            elif cmd == 'attack':
                # check collision with mob_ids
                entity.melee_attack(send_update=False)
            elif cmd == 'player_leaves':
                entity.kill()

    def receive_updates(self):
        while True:
            data, address = self.sock_wrapper.recv_from()
            assert address == self.server
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
