import pygame

import entities
from utils import *


class Client:
    def __init__(self, sock: socket.socket, server: Address, sprite_groups: Dict[str, pygame.sprite.Group],
                 player_animations, player_anim_speed, mob_animations, mob_anim_speed, player_walk_speed,
                 mob_walk_speed):
        self.fernet = None
        self.serialized_public_key = None
        self.fernet_init()

        self.sock = sock
        self.sock_wrapper = JSONSocketWrapper(self.sock, self.fernet)
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

    def fernet_init(self):
        server_public_key = load_public_ecdh_key()
        client_private_key = ec.generate_private_key(CURVE)
        self.fernet = get_fernet(server_public_key, client_private_key)
        self.serialized_public_key = serialize_public_key(client_private_key.public_key())

    def send_data(self, data: bytes, dst):
        data = self.serialized_public_key + self.fernet.encrypt(data)
        self.sock.sendto(data, dst)

    def send_update(self, cmd: str, params: dict):
        self.send_data(json.dumps({'cmd': cmd, **params}).encode(), self.server)

    def create_entity(self, cls, data, sprite_groups, walk_speed, animations, anim_speed, **kwargs):
        entity = cls(
            pos=data['start_pos'], sprite_groups=sprite_groups, animations=animations, walk_speed=walk_speed,
            anim_speed=anim_speed, id_=data['id'], **kwargs)
        entity.health = data['health']
        entity.move(*data['end_pos'], send_update=False)
        for item_id, item_type in data.pop('items', {}).items():
            entities.Item(item_type=item_type, owner=entity, item_id=item_id)
        if ENABLE_SHADOWS:
            cls(
                pos=data['start_pos'], sprite_groups=[self.sprite_groups['all'], self.sprite_groups['shadows']],
                animations=animations, walk_speed=walk_speed, anim_speed=anim_speed, id_=data['id'] + 1, **kwargs)
        return entity

    def create_main_player(self, data):
        return self.create_player(data, cls=entities.MainPlayer, sock_client=self)

    def create_player(self, data, cls=entities.Player, **kwargs):
        return self.create_entity(cls=cls, data=data, sprite_groups=self.player_sprite_groups,
                                  walk_speed=self.player_walk_speed, animations=self.player_animations,
                                  anim_speed=self.player_anim_speed, **kwargs)

    def create_mob(self, data):
        return self.create_entity(cls=entities.Entity, data=data, sprite_groups=self.entity_sprite_groups,
                                  walk_speed=self.mob_walk_speed, anim_speed=self.mob_anim_speed,
                                  animations=self.mob_animations[data['type']])

    def send_projectile(self, vect, proj_type):
        self.send_update(
            'projectile',
            {'id': self.main_player.id,
             'projectile': {'target': list(vect), 'type': proj_type, 'attacker_id': self.main_player.id}})

    def create_projectile(self, data):
        entities.Projectile(proj_type=data['type'], attacker=self.get_entity_by_id(data['attacker_id']),
                            sprite_groups=self.projectile_sprite_groups, vect=pygame.Vector2(data['target']),
                            id_=data['id'])

    def create_dropped(self, data):
        entities.Dropped(item_type=data['item_type'], pos=data['pos'], sprite_groups=self.dropped_sprite_groups,
                         item_id=data['item_id'])

    def connect(self, username='ariel'):
        self.send_update('connect', {'username': username})
        data, address = self.sock_wrapper.recv_from()
        assert address == self.server
        self.init(data)

    def init(self, data):
        logging.debug(f'init data received: {data=}')
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

    def get_projectile_by_id(self, id_: int):
        sprites = self.sprite_groups['projectiles'].sprites()
        ids = [sprite.id for sprite in sprites]
        return sprites[ids.index(id_)] if id_ in ids else None

    def get_entity_by_id(self, id_: int):
        sprites = self.sprite_groups['entity'].sprites()
        ids = [sprite.id for sprite in sprites]
        return sprites[ids.index(id_)] if id_ in ids else None

    def get_dropped_by_id(self, id_: int):
        sprites = self.sprite_groups['dropped'].sprites()
        ids = [sprite.item_id for sprite in sprites]
        return sprites[ids.index(id_)] if id_ in ids else None

    def get_shadow_by_id(self, id_: int):
        sprites = self.sprite_groups['shadows'].sprites()
        ids = [sprite.id for sprite in sprites]
        return sprites[ids.index(id_)] if id_ in ids else None

    def handle_collision(self, collision_data):
        id1, id2 = collision_data['id1'], collision_data['id2']
        o1, o2 = None, None
        if id1 is not None:
            o1 = self.get_entity_by_id(id1)
            if o1 is None:
                o1 = self.get_projectile_by_id(id1)
        if id2 is not None:
            o2 = self.get_entity_by_id(id2)
            if o2 is None:
                o2 = self.get_projectile_by_id(id2)

        if o1 is not None and collision_data['aligned1'] is not None:
            o1.move(*collision_data['aligned1'], send_update=False)
        if o2 is not None and collision_data['aligned2'] is not None:
            o2.move(*collision_data['aligned2'], send_update=False)

        if o1 is not None and isinstance(o1, entities.Entity):
            o1.health -= collision_data['damage1']
        if o2 is not None and isinstance(o2, entities.Entity):
            o2.health -= collision_data['damage2']
        elif o2 is not None and isinstance(o2, entities.Projectile):
            o2.kill()

    def handle_update(self, update: dict):
        cmd = update['cmd']
        player_ids = [player.id for player in self.sprite_groups['players'].sprites()]
        if cmd == 'player_enters':
            if update['player']['id'] not in player_ids:
                self.create_player(update['player'])
        elif cmd == 'projectile':
            self.create_projectile(update['projectile'])
        elif cmd == 'collisions':
            for collision_data in update['collisions_data']:
                self.handle_collision(collision_data)
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
            entity = self.get_entity_by_id(update['id'])
            entity.handle_death()
            for drop_data in update['drops']:
                self.create_dropped(drop_data)
        elif cmd == 'use_skill':
            entity = self.get_entity_by_id(update['id'])
            entity.use_skill(skill_id=update['skill_id'], sprite_groups=self.sprite_groups, inv=None,
                             extra=update['extra'])
        elif ENABLE_SHADOWS and cmd == 'shadows':
            for entity in update['entities']:
                shadow = self.get_shadow_by_id(entity['id'] + 1)
                shadow.rect.center = entity['pos']
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
