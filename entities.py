import logging
import random
import time
from typing import Iterable
import sys
import pygame as pg

import client
import collections
from settings import *
from client_chat import *


class Entity(pg.sprite.Sprite):
    def __init__(self, pos, sprite_groups: Iterable[pg.sprite.Group], animations, walk_speed, anim_speed, id_: int,
                 auto_move=False):
        self.groups = sprite_groups
        # self.groups[0]: all sprites, self.groups[1]: entity sprites
        self.id = id_
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

        # add to sprite groups after all fields are initialized to avoid race conditions
        pg.sprite.Sprite.__init__(self, *self.groups)

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
                        map_rect.width * MAP_COEFFICIENT),
                    min(max(round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t), 0),
                        map_rect.height * MAP_COEFFICIENT))
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
        self.kill()


class Player(Entity):
    def __init__(self, pos, sprite_groups, animations, walk_speed, anim_speed, id_):
        Entity.__init__(self, pos, sprite_groups, animations, walk_speed, anim_speed, id_)

    def update(self, map_rect, sprite_groups):
        Entity.update(self, map_rect, sprite_groups)

    def use_skill(self, skill_id, sprite_groups, inv, send_update=True):
        """
        SKILL 1: CIRCLE OF AXES THROWN AROUND PLAYER
        SKILL 2: BUFFS: GETS TEMP STRENGTH, TEMP SPEED AND INSTANT HEAL
        SKILL 3: GETS THREE POTIONS (INSERTS TO INVENTORY)

        ONLY SENDS TYPE OF SKILL TO SERVER TO MINIMIZE PACKET TRAFFIC
        """
        if not send_update:
            # CHECK WHICH SKILL BY ID:
            if skill_id == 1:
                vect = pg.math.Vector2(0, 1)
                for i in range(0, 9):
                    # CIRCLE OF AXES:

                    axe = Projectile("axe", self, vect, [sprite_groups["all"], sprite_groups["projectiles"]],
                                     send_update=False)
                    vect = vect.rotate(45)
            elif skill_id == 2:
                # BUFFS USING (INSTANTLY USED) ITEMS:

                speed_pot = Item("speed_pot", self)
                strength_pot = Item("strength_pot", self)
                heal_pot = Item("heal_pot", self)
                speed_pot.use_item(send_update=False)
                strength_pot.use_item(send_update=False)
                heal_pot.use_item(send_update=False)
        if send_update and skill_id == 3:
            # GET POTIONS IN INVENTORY:

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
        self.client = sock_client
        self.cooldowns = {'skill': 0, 'projectile': 0}
        super(MainPlayer, self).__init__(*args, **kwargs)

    def is_cooldown_over(self, action):
        return time.time_ns() > self.cooldowns[action]

    def move(self, x, y, send_update=True):
        super(MainPlayer, self).move(x, y)
        if send_update:
            self.client.send_update('move', {'id': self.id, 'pos': [x, y]})

    def melee_attack(self, send_update=True):
        super(MainPlayer, self).melee_attack()
        if send_update:
            self.client.send_update('attack', {'id': self.id})
            
    def projectile_attack(self, proj_type, sprite_groups):
        if self.is_cooldown_over('projectile'):
            vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, pg.mouse.get_pos()[1] - HEIGHT // 2)
            Projectile(proj_type, self, vect, [sprite_groups["all"], sprite_groups["projectiles"]])
            self.cooldowns['projectile'] = time.time_ns() + 10 ** 9
            
    def use_skill(self, skill_id, sprite_groups, inv, send_update=True):
        if self.is_cooldown_over('skill'):
            super(MainPlayer, self).use_skill(skill_id, sprite_groups, inv, send_update=send_update)
            if send_update:
                self.client.send_update('use_skill', {'id': self.id, 'skill_id': skill_id})
            else:
                self.cooldowns['skill'] = time.time_ns() + 10 * 10 ** 9

    def drop_item(self, inv, sprite_groups, send_update=True):
        """ DROPS ITEM FROM CURRENT SLOT ON THE GROUND"""
        item = inv.slots[inv.cur_slot]
        # CHECK IF CUR SLOT IS EMPTY:
        if item != 0:
            # REMOVE FROM INVENTORY
            inv.remove_item(inv.cur_slot)
            # CHECK IN WHICH DIRECTION TO DROP ITEM:
            if self.direction == 1:
                pos = self.rect.topleft
            else:
                pos = self.rect.topright
            if send_update:
                self.client.send_update('item_dropped',
                                        {'item_id': item.item_id, 'id': self.id, 'pos': self.rect.center})
            item.kill()

    def pick_item(self, inv: 'Inventory', sprite_groups, send_update=True):
        """" PICKS UP ITEM:
        CHECKS IF INVENTORY IS FULL,
        CHECKS COLLISION WITH DROPPED ITEMS,
        REMOVES DROPPED ITEM FROM ITS GROUPS AND ADDS ITEM TO INVENTORY"""

        # CHECK INV:
        if inv.is_full():
            print("INV FULL")
            return

        # GO OVER ALL DROPPED ITEMS:
        for sprite in sprite_groups["dropped"]:
            # CHECK COLLISION WITH PLAYER:
            if pg.sprite.collide_rect(self, sprite):
                # ADD ITEM TO INV AND PLAYER ITEMS:
                item = Item(sprite.item_type, self, sprite.item_id)
                inv.add_item(item)
                self.items.add(item)
                if send_update:
                    self.client.send_update('item_picked', {'id': self.id, 'item_id': item.item_id})

    def use_item(self, inv, sprite_groups, send_update=True):
        """ USES ITEM FROM CURRENT SLOT"""
        item = inv.slots[inv.cur_slot]
        # CHECK IF CUR SLOT IS EMPTY:
        if item != 0:
            # REMOVE FROM INVENTORY
            inv.remove_item(inv.cur_slot)
            # CHECK IN WHICH DIRECTION TO DROP ITEM:
            if send_update:
                self.client.send_update('use_item', {'item_id': item.item_id, 'id': self.id})
            item.kill()

    def handle_death(self):
        super(MainPlayer, self).handle_death()
        pg.quit()
        sys.exit()


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

    def __init__(self, item_type, owner: Entity, item_id=1):
        self.group = owner.items
        self.item_type = item_type
        self.item_id = item_id
        self.owner = owner
        self.image = pg.image.load('graphics/items/' + item_type + ".png")
        self.rect = self.image.get_rect()
        self.duration = 0  # duration of item's effect to last

        pg.sprite.Sprite.__init__(self, self.group)

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
            self.owner.client.send_update('use_item', {'id': self.owner.id, 'item_type': self.item_type})

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


class Dropped(pg.sprite.Sprite):
    def __init__(self, item_type: str, pos: tuple, sprite_groups, item_id: int = 1):
        self.groups = sprite_groups
        self.item_id = item_id
        self.item_type = item_type
        self.image = pg.image.load('graphics/items/' + item_type + ".png")
        self.rect = self.image.get_rect()
        self.rect.topleft = pos
        pg.sprite.Sprite.__init__(self, *self.groups)

    def update(self, *args):
        pass

    def draw(self, screen, camera):
        screen.blit(self.image, camera.apply(self))


class Inventory:
    def __init__(self, screen_size, weapon_held=0):
        self.slots = [0 for _ in range(INVENTORY_SIZE)]
        self.weapons = ['sword', 'arrow', 'axe']
        self.weapons_img = [pg.image.load(f"./Graphics/weapons/{w}.png") for w in self.weapons]
        
        self.image = pg.image.load("Graphics/Inventory.png")
        self.rect = self.image.get_rect()
        self.rect.bottom = screen_size[1]
        self.rect.centerx = screen_size[0] // 2
        
        self.slot_img = pg.image.load("Graphics/cur_slot.png")
        self.special_slot_img = pg.image.load("Graphics/slot.png")
        self.cur_slot = 0  # current slot
        
        self.font = pg.font.Font(pg.font.get_default_font(), 25)
        
        self.weapon_held = weapon_held
        self.weapon_img = self.weapons_img[self.weapon_held]

    def render(self, screen):
        # DRAW INVENTORY:
        screen.blit(self.image, self.rect)

        # DRAW SLOTS AND ITEMS:
        for i in range(INVENTORY_SIZE):
            text = self.font.render(str(i + 1), True, (0, 0, 0))
            screen.blit(text, (self.rect.midleft[0] + i * 40, self.rect.midleft[1]))  # NUM

            # CHECK IF SLOT IS EMPTY:
            if self.slots[i] == 0:
                continue

            # DRAW ITEM:
            screen.blit(self.slots[i].image, (self.rect.topleft[0] + i * 40, self.rect.topleft[1]))

        # DRAW OUTLINE AROUND CURRENT SLOT:
        screen.blit(self.slot_img, (self.rect.topleft[0] + self.cur_slot * 40, self.rect.topleft[1]))

        # DRAW SPECIAL SLOT
        screen.blit(self.special_slot_img, (self.rect.topleft[0] - 60, self.rect.topleft[1]))
        # DRAW SPECIAL ITEM (WEAPON HELD)
        screen.blit(self.weapon_img, (self.rect.topleft[0] - 65, self.rect.topleft[1]))

    def is_full(self):
        """ RETURNS TRUE IF INVENTORY IS FULL, IF NO SLOTS AVAILABLE RETURNS FALSE"""
        for i in range(INVENTORY_SIZE):
            if self.slots[i] == 0:
                return False
        return True

    def add_item(self, item: Item, send_updates=False):
        """" ADD ITEM TO FIRST EMPTY SLOT"""
        for i in range(INVENTORY_SIZE):
            if self.slots[i] == 0:
                self.slots[i] = item
                return
        # NO SLOT AVAILABLE:
        print("INVENTORY FULL")

    def remove_item(self, slot: int):
        """" REMOVE ITEM FROM INVENTORY BY SLOT NUMBER"""
        if self.slots[slot] != 0:
            self.slots[slot] = 0
            return
        else:
            print("SLOT EMPTY")

    def switch_weapon(self):
        """ SWITCHES WEAPON HELD AT SPECIAL SLOT"""
        self.weapon_held = (self.weapon_held + 1) % len(self.weapons)
        self.weapon_img = self.weapons_img[self.weapon_held]
        return


class Projectile(pg.sprite.Sprite):
    """" PROJECTILE CLASS. GETS TYPE OF PROJECTILE, ATTACKER (PLAYER/MOB), TARGET VECTOR, ALL_SPRITE_GROUPS
         TARGET VECTOR IS SCREEN VECTOR FROM PLAYER TO MOUSE """

    def __init__(self, proj_type, attacker: Entity, vect: pg.math.Vector2, sprite_groups, send_update=True):
        self.groups = sprite_groups
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
            self.image = pg.transform.rotate(self.image, 230 - self.angle)  # ROTATE SO IT'S FACING IN ITS DIRECTION
        elif proj_type == 'axe':
            self._speed = 10
            self.damage = 20
            self.image = pg.transform.rotate(self.image, 310 - self.angle)
        else:
            self.image = pg.transform.rotate(self.image, self.angle)
            self._speed = 10
            self.damage = 20

        # X,Y AXIS SPEEDS:
        self._speed_x = (vect.x / vect.length()) * self._speed
        self._speed_y = (vect.y / vect.length()) * self._speed

        self._i = 0  # ITERATION

        # add to sprite groups ONLY after all fields are initialized (to avoid race conditions with the game thread)
        pg.sprite.Sprite.__init__(self, sprite_groups)

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
        if self.rect.centerx > map_rect.width * MAP_COEFFICIENT * MAP_COEFFICIENT or self.rect.centerx < 0 or self.rect.centery > map_rect.height * MAP_COEFFICIENT * MAP_COEFFICIENT or self.rect.centery < 0:
            self.remove(self.groups)

        # CHECK COLLISION WITH ENTITIES:
        for sprite in sprite_groups['entity']:  # groups[1] - all entities (players/mobs)
            if sprite is not self.attacker and pg.sprite.collide_rect(self, sprite):
                if not self.alive():
                    return
                logging.debug(f'player-projectile collision: {sprite.id=}, {sprite.health=}')
                sprite.health -= self.damage
                self.kill()
                return

    def draw(self, screen, camera):
        screen.blit(self.image, camera.apply(self))


class Chat(pg.sprite.Sprite):
    """"
    CHAT CLASS:
    LINES WRITTEN IN TOPLEFT OF SCREEN
    USING FIRST IN FIRST OUT QUEUE FOR LINES
    CHAT MAY BE INITIALIZED WITH AN ALREADY MADE QUEUE OF LINES,
    OTHERWISE STARTS AS EMPTY CHAT
    """

    def __init__(self, client_chat, lines=collections.deque([]), username=''):
        pg.sprite.Sprite.__init__(self)
        self.client_chat = client_chat
        self.font = pg.font.Font(pg.font.get_default_font(), 25)
        self.lines = lines
        self.cur_typed = ''  # LINE BEING TYPED BY CLIENT
        self.color = BLACK
        self.is_pressed = False  # WHETHER BUTTON TO CHAT HAS BEEN PRESSED OR NOT
        if username != '':
            self.username = username + ': '  # if username given add it (for cur typed)
        else:
            self.username = username  # empty string

    def add_line(self, line: str):
        # CHECK IF CHAT NOT FULL:
        if len(self.lines) < 8:
            self.lines.append(line)
        else:
            # IF FULL, REMOVE LAST LINE AND INSERT NEW LINE AS FIRST
            self.lines.popleft()  # FIRST IN FIRST OUT
            self.lines.append(line)  # ADD NEW LINE

    def send_line(self, line):
        # ADD LINE TO OWN CHAT:
        if len(line) > char_lim:
            logging.debug(f'unable to send line, character limit reached')
            return
        self.client_chat.send(line)

    def update(self, screen):
        # BLIT EVERY LINE TOP LEFT OF SCREEN:
        count = 0
        for line in self.lines:
            text = self.font.render(line, True, self.color)
            screen.blit(text, (0, count * 20))
            count += 1

        # PRINT CURRENTLY TYPED LINE IF THERE IS ONE:
        if self.cur_typed != '':
            try:
                text = self.font.render(self.username + self.cur_typed, True, self.color)
                screen.blit(text, (0, count * 20))
            except ValueError:
                logging.error('unable to render text')
