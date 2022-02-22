import pygame as pg
from random import randint
from os import path
from animated_sprite import AnimatedSprite
from settings import *
from Tilemap import *

pg.init()
WIDTH, HEIGHT = 1280, 720
BLACK, RED = "#000000", "#FF0000"


class Player(pg.sprite.Sprite):
    def __init__(self, pos, all_sprites):
        self.groups = all_sprites
        pg.sprite.Sprite.__init__(self, self.groups)

        self.walk_speed = 5
        self._start, self._end = (0, 0), (0, 0)
        self._i = 0
        self._t = 1
        self.status = 'idle'
        self.animations = {
            'idle': AnimatedSprite('graphics/Knight/KnightIdle_strip.png', 15),
            'run': AnimatedSprite('graphics/Knight/KnightRun_strip.png', 8),
            'death': AnimatedSprite('graphics/Knight/KnightDeath_strip.png', 15)
        }
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
        self.animation = self.animations[self.status]

    def update(self):
        """"
            UPDATES PLAYER LOCATION:
            for each iteration update pos by averaging the 'start' and 'end' for each axis
        """
        # TODO: check dt
        if self.health <= 0:
            self.change_status('death')
            # TODO: fix death
            return
        # for testing health:
        if self.health < 100:
            self.health += 0.1

        # RUNNING CALCULATIONS

        if self.status == 'run':
            if self._i < self._t:
                self.rect.center = (round(self._start[0] + (self._end[0] - self._start[0]) * self._i / self._t),
                            round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t))
                self._i += 1

            else:
                self.rect.center = self._end
                self.change_status('idle')

        if self.animation_tick % 4 == 0:
            self.animation.update()

        self.animation_tick += 1
        self.image = self.animation.image

        if self.direction:
            self.image = pg.transform.flip(self.image, True, False)

def handle_keyboard(player, key):
    """"handle the keyboard inputs"""
    key = pg.key.name(key)
    if key == '=' and player.health < 100:
        player.health += 10
    elif key == '-' and player.health > 0:
        player.health -= 10


def events(player):
    for event in pg.event.get():
        if event.type == pg.QUIT:
            return False
        if event.type == pg.KEYDOWN:
            handle_keyboard(player, event.key)
        if event.type == pg.MOUSEBUTTONDOWN:
            mouse = pg.mouse.get_pos()

            # CHANGE DIRECTION (0 = RIGHT, 1 = LEFT)
            if mouse[0] >= WIDTH // 2:
                player.direction = 0
            else:
                player.direction = 1
            
            # MOVE THE PLAYER ACCORDING TO MOUSE POS
            player.move(mouse[0] - WIDTH // 2, mouse[1] - HEIGHT // 2)
    return True


def update(all_sprites, player, camera):

    for sprite in all_sprites:
        sprite.update()

    camera.update(player)


def draw(screen, all_sprites, map_img, map_rect, camera):
    screen.fill(BGCOLOR)

    screen.blit(map_img, camera.apply_rect(map_rect))

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite))

    pg.display.update()


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    all_sprites = pg.sprite.Group()

    player = Player((640, 360), all_sprites)

    # SETTING UP MAP

    map_folder = 'maps'

    tiled_map = TiledMap(path.join(map_folder, 'map_new.tmx'))
    map_img = tiled_map.make_map()
    map_rect = map_img.get_rect()

    # SETTING UP CAMERA
    
    camera = Camera(tiled_map.width, tiled_map.height)


    running = True
    while running:
        running = events(player)
        update(all_sprites, player, camera)
        draw(screen, all_sprites, map_img, map_rect, camera)
        clock.tick(FPS)


    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
