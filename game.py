import pygame as pg
from random import randint, randrange, choice
from os import path
from animated_sprite import AnimatedSprite
from settings import *
from Tilemap import *
import math


pg.init()


class Projectile(pg.sprite.Sprite):
    """" PROJECTILE CLASS. GETS TYPE OF PROJECTILE, ATTACKER (PLAYER/MOB), TARGET VECTOR, SPRITE_GROUPS"""
    def __init__(self, type, attacker, vect: pg.math.Vector2, sprite_groups):
        self.groups = sprite_groups
        pg.sprite.Sprite.__init__(self, self.groups)

        self._start = attacker.rect.center
        self.image = pg.image.load('graphics/projectiles/' + type + ".png")
        self.rect = self.image.get_rect(topleft=self._start)
        self.angle = vect.as_polar()[1]  # VECTOR ANGLE

        # CHECK EACH TYPE:
        if type == 'arrow':
            self._speed = 10
            self.damage = 20
            self.image = pg.transform.rotate(self.image, 230 + self.angle)  # ROTATE SO IT'S FACING IN ITS DIRECTION
        elif type == 'axe':
            self._speed = 10
            self.damage = 20
            self.image = pg.transform.rotate(self.image, 310 + self.angle)
        else:
            self._speed = 10
            self.damage = 20

        # X,Y AXIS SPEEDS:
        self._speed_x = (vect.x / vect.length()) * self._speed
        self._speed_y = - (vect.y / vect.length()) * self._speed

        self._i = 0  # ITERATION

    def update(self, map_rect):
        """" UPDATES PROJECTILE: RECT POS, BORDER AND ENTITY COLLISIONS"""
        # TODO: check collision with enemy

        # UPDATE POS WITH EACH AXIS SPEED BY ITERATION:
        self._i += 1
        self.rect.center = self._start[0] + (self._speed_x * self._i),  self._start[1] + (self._speed_y * self._i)
        # CHECK BORDERS:
        if self.rect.centerx > map_rect.width or self.rect.centerx < 0 or self.rect.centery > map_rect.height or self.rect.centery < 0:
            self.remove(self.groups)

    def draw(self, screen, camera):
        screen.blit(self.image, camera.apply(self))


class Entity(pg.sprite.Sprite):
    def __init__(self, pos, sprite_groups, animations, walk_speed, anim_speed, auto_move=False):
        self.groups = sprite_groups
        pg.sprite.Sprite.__init__(self, self.groups)

        self.walk_speed = walk_speed
        self.anim_speed = anim_speed
        self.auto_move = auto_move
        self._start, self._end = (pos[0], pos[1]), (pos[0], pos[1])
        self._i = 0
        self._t = 1
        self.status = 'idle'
        self.animations = animations
        self.animation = self.animations[self.status]
        self.image = pg.Surface((TILESIZE, TILESIZE))
        self.rect = self.image.get_rect(topleft=pos)
        self.normal_image = self.image
        self.image.fill((255, 0, 0))
        self.direction = 0
        self.animation_tick = 0
        self.animation_speed = 1  # TODO: do something with this
        self.health = 100

    def move(self, x, y):
        self.change_status('run')
        self._start = self.rect.center
        self._end = self._start[0] + x, self._start[1] + y
        dist = ((self._end[0] - self._start[0]) ** 2 + (self._end[1] - self._start[1]) ** 2) ** 0.5
        self._t = dist / self.walk_speed
        self._i = 0

    def change_status(self, status):
        self.status = status
        self.animations[self.status].surface_index = 0
        self.animation = self.animations[self.status]

    def update(self, map_rect):
        """"
            UPDATES PLAYER LOCATION:
            for each iteration update pos by averaging the 'start' and 'end' for each axis
        """
        # TODO: check dt
        if self.auto_move and randrange(1, 100) == 1:
            dir_x = randrange(-80, 80)
            if dir_x < 0:
                self.direction = 1
            else:
                self.direction = 0
            self.move(dir_x, randrange(-80, 80))
        
        if self.health <= 0:
            self.change_status('death')
            # TODO: fix death
            return
        
        # RUNNING CALCULATIONS

        if self.status == 'run':
            if self._i < self._t:
                # UPDATE RECT AND BORDERS COLLISION CHECK:
                self.rect.center = (min(max(round(self._start[0] + (self._end[0] - self._start[0]) * self._i / self._t), 0), map_rect.width),
                                    min(max(round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t), 0), map_rect.height))
                self._i += 1

            else:
                self.rect.center = self._end
                self.change_status('idle')
            
        if self.animation_tick % self.anim_speed == 0:
            self.animation.update()

        self.animation_tick += 1
        self.image = self.animation.image

        if self.direction:
            self.image = pg.transform.flip(self.image, True, False)
            
        if self.status == 'attack':
            if self.animation.surface_index == len(self.animation.surfaces) - 1:
                print("FINISHED ATTACKING")
                self.change_status('idle')

    def draw(self, screen, camera):
        screen.blit(self.image, camera.apply(self))
        pg.draw.line(screen, (255, 0, 0),
                     (camera.apply(self).topleft[0], camera.apply(self).topleft[1] - 20),
                     (camera.apply(self).topleft[0] + self.health, camera.apply(self).topleft[1] - 20))
    
    def melee_attack(self):
        if self.status == "attack": # CHECK IF ALREADY ATTACKING
            return
        self.change_status('attack')
    

def handle_keyboard(player, key):
    if key == 120: # X KEY
        print("ATTACKING")
        player.melee_attack()
    elif key == 122:  # Z key
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2,  HEIGHT // 2 - pg.mouse.get_pos()[1])
        axe = Projectile("axe", player, vect, player.groups)
    elif key == 99:  # C KEY
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2,  HEIGHT // 2 - pg.mouse.get_pos()[1])
        arrow = Projectile("arrow", player, vect, player.groups)


def events(player, camera):
    for event in pg.event.get():
        if event.type == pg.QUIT:
            return False
        if event.type == pg.KEYDOWN:
            handle_keyboard(player, event.key)
        if event.type == pg.MOUSEBUTTONDOWN:
            mouse = pg.mouse.get_pos()

            # CHANGE DIRECTION (0 = RIGHT, 1 = LEFT)
            if mouse[0] >= camera.apply(player).topleft[0]:
                player.direction = 0
            else:
                player.direction = 1
            
            # MOVE THE PLAYER ACCORDING TO MOUSE POS
            player.move(mouse[0] - camera.apply(player).topleft[0],
                        mouse[1] - camera.apply(player).topleft[1])
            print(player._end)
    return True


def update(all_sprites, player, camera, map_rect):

    for sprite in all_sprites:
        sprite.update(map_rect)

    camera.update(player)


def draw(screen, all_sprites, map_img, map_rect, camera):
    screen.fill(BGCOLOR)

    screen.blit(map_img, camera.apply_rect(map_rect))

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite))
        sprite.draw(screen, camera)

    pg.display.update()


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    all_sprites = pg.sprite.Group()
    
    player_anims = {
        'idle': AnimatedSprite('graphics/Knight/KnightIdle_strip.png', 15, True),
        'run': AnimatedSprite('graphics/Knight/KnightRun_strip.png', 8, True),
        'death': AnimatedSprite('graphics/Knight/KnightDeath_strip.png', 15, True),
        'attack': AnimatedSprite('graphics/Knight/KnightAttack_strip.png', 22, True)
    }
    mob_anims = [
        {
            'idle': AnimatedSprite('graphics/small_dragon/Idle', 3, False),
            'run': AnimatedSprite('graphics/small_dragon/Walk', 4, False),
            'death': AnimatedSprite('graphics/Knight/KnightDeath_strip.png', 15, True)
        }
    ]

    player = Entity((1400, 1360), [all_sprites], player_anims, 5, 5)
    mob = Entity((1600, 1390), [all_sprites], choice(mob_anims), 2, 15, auto_move=True)

    # SETTING UP MAP

    map_folder = 'maps'

    tiled_map = TiledMap(path.join(map_folder, 'map_new.tmx'))
    map_img = tiled_map.make_map()
    map_rect = map_img.get_rect()

    # SETTING UP CAMERA
    
    camera = Camera(tiled_map.width, tiled_map.height)


    running = True
    while running:
        running = events(player, camera)
        update(all_sprites, player, camera, map_rect)
        draw(screen, all_sprites, map_img, map_rect, camera)
        clock.tick(FPS)

    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
