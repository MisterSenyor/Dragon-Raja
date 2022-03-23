import random
from typing import Iterable

import pygame as pg

import client
from settings import *


class Entity(pg.sprite.Sprite):
    def __init__(self, pos, sprite_groups: Iterable[pg.sprite.Group], animations, walk_speed, anim_speed,
                 auto_move=False, id_: int = None):
        self.groups = sprite_groups
        pg.sprite.Sprite.__init__(self, *self.groups)
        # self.groups[0]: all sprites, self.groups[1]: entity sprites
        self.id = id_ if id_ is not None else random.randint(0, 1000000)
        self.items = pg.sprite.Group()
        self.walk_speed = walk_speed
        self.anim_speed = anim_speed
        self.auto_move = auto_move
        self._start, self._end = (pos[0], pos[1]), (pos[0], pos[1])
        self.attack_dmg = 20
        self._i = 0
        self._t = 1
        self._has_hit = 0  # FOR MELEE ATTACKS. ONCE ENTITY HITS TARGET CHANGES BACK TO 1
        self.status = 'idle'
        self.animations = animations
        self.animation = self.animations[self.status]
        self.image = pg.Surface((TILESIZE, TILESIZE))
        self.rect = self.image.get_rect(topleft=pos)
        self.normal_image = self.image
        self.image.fill((255, 0, 0))
        self.direction = 0
        self.animation_tick = 0
        self.health = 100

    def move(self, x, y, send_update=True):
        if self.status != 'attack':
            self.change_status('run')  # CHANGE STATUS TO RUN UNLESS ATTACKING
        self._start = self.rect.center
        self._end = x, y
        dist = ((self._end[0] - self._start[0]) ** 2 + (self._end[1] - self._start[1]) ** 2) ** 0.5
        self._t = dist / self.walk_speed
        self._i = 0

    def change_status(self, status):
        self.status = status
        self.animations[self.status].surface_index = 0
        self.animation = self.animations[self.status]

    def update(self, map_rect, sprite_groups):
        """"
        UPDATES PLAYER LOCATION:
        for each iteration update pos by averaging the 'start' and 'end' for each axis
        """
        for item in self.items:
            item.update()
        if self.health <= 0:
            self.handle_death()
            return
        # TODO: check dt
        if self.auto_move and random.randrange(1, 100) == 1:
            dir_x = random.randrange(-80, 80)
            if dir_x < 0:
                self.direction = 1
            else:
                self.direction = 0
            self.move(dir_x, random.randrange(-80, 80))
        # RUNNING CALCULATIONS
        if self.status == 'run' or self.status == 'attack':
            if self._i < self._t:
                # UPDATE RECT AND BORDERS COLLISION CHECK:
                self.rect.center = (
                    min(max(round(self._start[0] + (self._end[0] - self._start[0]) * self._i / self._t), 0),
                        map_rect.width),
                    min(max(round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t), 0),
                        map_rect.height))
                self._i += 1
            else:
                self.rect.center = self._end
                self._t = 0
                if self.status == 'run':  # IF RUNNING (NOT ATTACKING) HAS ENDED, CHANGE BACK TO IDLE
                    self.change_status('idle')
        if self.animation_tick % self.anim_speed == 0:
            self.animation.update()
        self.animation_tick += 1
        self.image = self.animation.image
        if self.direction:
            self.image = pg.transform.flip(self.image, True, False)
        if self.status == 'attack':
            # CHECK IF ATTACK IS FINISHED:
            if self.animation.surface_index == len(self.animation.surfaces) - 1:
                print("FINISHED ATTACKING")
                self.anim_speed += 3  # RETURN PREV ANIMATION SPEED
                if self._t == 0:  # IF NOT IN THE MIDDLE OF RUN
                    self.change_status('idle')
                else:
                    self.change_status('run')
            # CHECK COLLISION WITH ENTITIES:
            if not self._has_hit:  # if player hasn't already hit a target with this attack:
                for sprite in sprite_groups['entity']:  # groups[1] - all entities (players/mobs)
                    if sprite is not self and pg.sprite.collide_rect(self, sprite):
                        sprite.health -= self.attack_dmg
                        self._has_hit = 1

    def draw(self, screen, camera):
        screen.blit(self.image, camera.apply(self))
        pg.draw.line(screen, (255, 0, 0),
                     (camera.apply(self).topleft[0], camera.apply(self).topleft[1] - 20),
                     (camera.apply(self).topleft[0] + self.health, camera.apply(self).topleft[1] - 20))

    def melee_attack(self, send_update=True):
        if self.status == "attack":  # CHECK IF ALREADY ATTACKING
            return
        self._has_hit = 0  # CHANGE TO HASN'T HIT ALREADY
        self.anim_speed -= 3
        self.change_status('attack')

    def handle_death(self):
        self.change_status('death')
        self.remove(self.groups)


class Player(Entity):
    def __init__(self, pos, sprite_groups, animations, walk_speed, anim_speed):
        Entity.__init__(self, pos, sprite_groups, animations, walk_speed, anim_speed)

    def update(self, map_rect, sprite_groups):
        Entity.update(self, map_rect, sprite_groups)

    def use_skill(self, skill_id, sprite_groups, inv):
        if skill_id == 1:
            vect = pg.math.Vector2(0, 1)
            for i in range(0, 9):
                axe = Projectile("axe", self, vect, [sprite_groups["all"], sprite_groups["projectiles"]], send_update=False)
                vect = vect.rotate(45)
        elif skill_id == 2:
            speed_pot = Item("speed_pot", self)
            strength_pot = Item("strength_pot", self)
            heal_pot = Item("heal_pot", self)
            speed_pot.use_item(send_update=False)
            strength_pot.use_item(send_update=False)
            heal_pot.use_item(send_update=False)
            heal_pot.use_item(send_update=False)
        elif skill_id == 3:
            speed_pot = Item("speed_pot", self)
            strength_pot = Item("strength_pot", self)
            heal_pot = Item("heal_pot", self)
            self.items.add(speed_pot)
            inv.add_item(speed_pot)
            self.items.add(strength_pot)
            inv.add_item(strength_pot)
            self.items.add(heal_pot)
            inv.add_item(heal_pot)


class MainPlayer(Player):
    def __init__(self, sock_client: 'client.Client', *args, **kwargs):
        super(MainPlayer, self).__init__(*args, **kwargs)
        self.client = sock_client

    def move(self, x, y, send_update=True):
        super(MainPlayer, self).move(x, y)
        if send_update:
            self.client.send_update('move', {'id': self.id, 'pos': [x, y]})

    def melee_attack(self, send_update=True):
        super(MainPlayer, self).melee_attack()
        if send_update:
            self.client.send_update('attack', {'id': self.id})

    def use_skill(self, skill_id, sprite_groups, inv, send_update=True):
        super(MainPlayer, self).use_skill(skill_id, sprite_groups, inv)
        if send_update:
            self.client.send_update('use_skill', {'id': self.id, 'skill_id': skill_id})


class Mob(Entity):
    def __init__(self, pos, sprite_groups, animations, walk_speed, anim_speed):
        self.RADIUS = 500
        self.counter = 0
        Entity.__init__(self, pos, sprite_groups, animations, walk_speed, anim_speed)

    def update(self, map_rect, sprite_groups):
        for player in sprite_groups["players"]:
            if player.rect.topright[0] >= self.rect.topright[0] - self.RADIUS:
                if player.rect.topleft[0] <= self.rect.topleft[0] + self.RADIUS:
                    if player.rect.topright[1] >= self.rect.topright[1] - self.RADIUS:
                        if player.rect.bottomright[1] <= self.rect.bottomright[1] + self.RADIUS:
                            x, y = player.rect.topright[0] - self.rect.topright[0], player.rect.topright[1] - \
                                   self.rect.topright[1]
                            if x:
                                x -= 100 * (abs(x) // x)
                            if y:
                                y -= 100 * (abs(y) // y)
                            if self.counter % 100 == 0:
                                self.counter = 0
                                self.move(self.rect.centerx + x, self.rect.centery + y)
                                mouse = pg.mouse.get_pos()
                                vect = pg.math.Vector2(player.rect.topleft[0] - self.rect.topleft[0],
                                                       self.rect.topleft[1] - player.rect.topleft[1])
                                axe = Projectile("axe", self, vect,
                                                 [sprite_groups["all"], sprite_groups["projectiles"]])
                            self.counter += 1
                            break

        else:
            if random.randrange(1, 100) == 1:
                dir_x = random.randrange(-80, 80)
                if dir_x < 0:
                    self.direction = 1
                else:
                    self.direction = 0
                self.move(dir_x, random.randrange(-80, 80))

        Entity.update(self, map_rect, sprite_groups)


class Item(pg.sprite.Sprite):
    """" ITEM CLASS, GETS ITEM TYPE, OWNER (ENTITY)"""
    def __init__(self, item_type, owner):
        self.group = owner.items
        pg.sprite.Sprite.__init__(self, self.group)
        self.item_type = item_type
        self.owner = owner
        self.image = pg.image.load('graphics/items/' + item_type + ".png")
        self.rect = self.image.get_rect()
        self.duration = 0  # duration of item's effect to last
        self.id = 0  # TODO - this is only temporary

    def use_item(self, send_update=True):
        """" USES ITEM. FOR EACH ITEM EXISTS A SPECIAL EFFECT AND DURATION"""
        if self.item_type == 'strength_pot':
            self.owner.attack_dmg += 10
            self.duration = 1000
        elif self.item_type == 'heal_pot':
            if self.owner.health < 80:
                self.owner.health += 20
            else:
                self.owner.health = 100
            self.remove(self.group)  # HEAL POT IS INSTANT. REMOVE FROM GROUP
        elif self.item_type == 'speed_pot':
            self.owner.walk_speed += 3
            self.duration = 1000
        elif self.item_type == 'useless_card':
            return
        else:
            self.owner.health = 100

        if isinstance(self.owner, MainPlayer) and send_update:
            self.owner.client.send_update('use_item', {'id': self.owner.id, 'item_id': self.id})

    def update(self):
        # DECREASE DURATION IN EACH TICK
        self.duration -= 1

        # CHECK IF DURATION ENDED:
        if self.duration == 0:

            # RESET EFFECT AND REMOVE FROM ITEM GROUP:
            if self.item_type == 'strength_pot':
                self.owner.attack_dmg -= 10
                self.duration = 100
            elif self.item_type == 'speed_pot':
                self.owner.walk_speed -= 3
                self.duration = 100
            self.remove(self.group)


class Inventory:
    def __init__(self):
        self.slots = []
        for i in range(0, 15):
            self.slots.append(0)
        self.image = pg.image.load("Graphics/Inventory.png")
        self.rect = self.image.get_rect()
        self.rect.topleft = (240, 640)
        self.slot_img = pg.image.load("Graphics/cur_slot.png")
        self.cur_slot = 0  # current slot
        self.font = pg.font.Font(pg.font.get_default_font(), 25)

    def render(self, screen):
        # DRAW INVENTORY:
        screen.blit(self.image, self.rect)

        # DRAW SLOTS AND ITEMS:
        for i in range(0, 15):
            text = self.font.render(str(i + 1), True, (0, 0, 0))
            screen.blit(text, (self.rect.midleft[0] + i * 40, self.rect.midleft[1]))  # NUM

            # CHECK IF SLOT IS EMPTY:
            if self.slots[i] == 0:
                continue

            # DRAW ITEM:
            screen.blit(self.slots[i].image, (self.rect.topleft[0] + i * 40, self.rect.topleft[1]))

        # DRAW OUTLINE AROUND CURRENT SLOT:
        screen.blit(self.slot_img, (self.rect.topleft[0] + self.cur_slot * 40, self.rect.topleft[1]))

    def add_item(self, item: Item, send_updates=False):
        """" ADD ITEM TO FIRST EMPTY SLOT"""
        for i in range(0, 15):
            if self.slots[i] == 0:
                self.slots[i] = item
                return
        print("INVENTORY FULL")

    def remove_item(self, slot: int):
        """" REMOVE ITEM FROM INVENTORY BY SLOT NUMBER"""
        if self.slots[slot] != 0:
            self.slots[slot] = 0
            return
        else:
            print("SLOT EMPTY")


class Projectile(pg.sprite.Sprite):
    """" PROJECTILE CLASS. GETS TYPE OF PROJECTILE, ATTACKER (PLAYER/MOB), TARGET VECTOR, ALL_SPRITE_GROUPS
         TARGET VECTOR IS SCREEN VECTOR FROM PLAYER TO MOUSE """

    def __init__(self, proj_type, attacker: Entity, vect: pg.math.Vector2, sprite_groups, send_update=True):
        self.groups = sprite_groups
        pg.sprite.Sprite.__init__(self, sprite_groups)
        # self.groups[0]: all sprites, self.groups[2]: projectile sprites

        self._start = attacker.rect.center
        self.attacker = attacker
        self.image = pg.image.load('graphics/projectiles/' + proj_type + ".png")
        self.rect = self.image.get_rect(topleft=self._start)
        self.angle = vect.as_polar()[1]  # VECTOR ANGLE

        # CHECK EACH TYPE:
        if proj_type == 'arrow':
            self._speed = 10
            self.damage = 20
            self.image = pg.transform.rotate(self.image, 230 + self.angle)  # ROTATE SO IT'S FACING IN ITS DIRECTION
        elif proj_type == 'axe':
            self._speed = 10
            self.damage = 20
            self.image = pg.transform.rotate(self.image, 310 + self.angle)
        else:
            self.image = pg.transform.rotate(self.image, self.angle)
            self._speed = 10
            self.damage = 20

        # X,Y AXIS SPEEDS:
        self._speed_x = (vect.x / vect.length()) * self._speed
        self._speed_y = - (vect.y / vect.length()) * self._speed

        self._i = 0  # ITERATION

        # send update to server
        if isinstance(self.attacker, MainPlayer) and send_update:
            self.attacker.client.send_update(
                'projectile',
                {'id': self.attacker.id,
                 'projectile': {'target': list(vect), 'type': proj_type, 'attacker_id': self.attacker.id}})

    def update(self, map_rect, sprite_groups):
        """" UPDATES PROJECTILE: RECT POS, BORDER AND ENTITY COLLISIONS"""

        # UPDATE POS WITH EACH AXIS SPEED BY ITERATION:
        self._i += 1
        self.rect.center = self._start[0] + (self._speed_x * self._i), self._start[1] + (self._speed_y * self._i)
        # CHECK BORDERS:
        if self.rect.centerx > map_rect.width or self.rect.centerx < 0 or self.rect.centery > map_rect.height or self.rect.centery < 0:
            self.remove(self.groups)

        # CHECK COLLISION WITH ENTITIES:
        for sprite in sprite_groups['entity']:  # groups[1] - all entities (players/mobs)
            if sprite is not self.attacker and pg.sprite.collide_rect(self, sprite):
                sprite.health -= self.damage
                self.remove(self.groups)

    def draw(self, screen, camera):
        screen.blit(self.image, camera.apply(self))
