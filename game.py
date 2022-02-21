import pygame as pg
from random import randint
from animated_sprite import AnimatedSprite
from settings import *

pg.init()
WIDTH, HEIGHT = 1280, 720
BLACK, RED = "#000000", "#FF0000"


class Tree(pg.sprite.Sprite):
    def __init__(self, pos, group):
        super().__init__(group)
        self.image = pg.image.load('Graphics/tree.png').convert_alpha()
        self.rect = self.image.get_rect(topleft=pos)


class Player(pg.sprite.Sprite):
    def __init__(self, pos, camera_group):
        super().__init__(camera_group)
        self.camera_group = camera_group
        super(Player, self).__init__()
        self.walk_speed = 5
        self._start, self._end = (0, 0), (0, 0)
        self._i = 0
        self._t = 1
        self.status = 'idle'
        self.animations = {
            'idle': AnimatedSprite('Graphics/Knight/KnightIdle_strip.png', 15),
            'run': AnimatedSprite('Graphics/Knight/KnightRun_strip.png', 8),
            'death': AnimatedSprite('Graphics/Knight/KnightDeath_strip.png', 15)
        }
        self.animation = self.animations[self.status]
        self.image = pg.Surface((TILESIZE, TILESIZE))
        self.rect = self.image.get_rect(topleft=pos)
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
        """" UPDATES PLAYER LOCATION:
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

        if self.status == 'run':
            if self._i < self._t:
                self.rect.center = (round(self._start[0] + (self._end[0] - self._start[0]) * self._i / self._t),
                            round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t))
                self.camera_group.offset = pg.Vector2(self.rect.center)
                self._i += 1
            else:
                self.rect.center = self._end
                self.change_status('idle')
        if self.animation_tick % 4 == 0:
            self.animation.update()
        self.animation_tick += 1
        self.image = self.animation.image


class CameraGroup(pg.sprite.Group):
    def __init__(self):
        super().__init__()
        self.display_surface = pg.display.get_surface()
        # camera offset
        self.offset = pg.math.Vector2()
        self.half_w = self.display_surface.get_size()[0] // 2
        self.half_h = self.display_surface.get_size()[1] // 2
        # ground
        self.ground_surf = pg.image.load('Graphics/ground.png').convert_alpha()
        self.ground_rect = self.ground_surf.get_rect(topleft=(0, 0))

    def custom_draw(self, player):
        self.center_target_camera(player)
        ground_offset = self.ground_rect.topleft - self.offset
        self.display_surface.blit(self.ground_surf, ground_offset)
        # active elements
        for sprite in sorted(self.sprites(), key=lambda sprite: sprite.rect.bottom):
            if sprite.__class__ is Player:
                self.draw_player(sprite)
                continue
            self.display_surface.blit(sprite.image, sprite.rect.center - self.offset)

    def draw_player(self, sprite: pg.sprite):
        # check direction:
        if sprite.direction == 1:  # left
            self.display_surface.blit(pg.transform.flip(sprite.image, True, False), (self.half_w, self.half_h))
            # HEALTH BAR:
            pg.draw.rect(self.display_surface, BLACK,
                         [sprite.rect.center[0] - self.offset[0] + 4, sprite.rect.center[1] - self.offset[1] + 4, 100,
                          8], 0)
            pg.draw.rect(self.display_surface, RED,
                         [sprite.rect.center[0] - self.offset[0] + 6, sprite.rect.center[1] - self.offset[1] + 6,
                          96 - (100 - sprite.health), 4], 0)
            return
        else:  # right
            self.display_surface.blit(sprite.image, sprite.rect.center - self.offset)
            # HEALTH BAR:
            pg.draw.rect(self.display_surface, BLACK,
                         [sprite.rect.center[0] - self.offset[0] + 4, sprite.rect.center[1] - self.offset[1] + 4, 100,
                          8], 0)
            pg.draw.rect(self.display_surface, RED,
                         [sprite.rect.center[0] - self.offset[0] + 6, sprite.rect.center[1] - self.offset[1] + 6,
                          96 - (100 - sprite.health), 4], 0)
            return

    def center_target_camera(self, target):
        self.offset.x = target.rect.centerx - self.half_w
        self.offset.y = target.rect.centery - self.half_h


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
            player.move(mouse[0] - WIDTH // 2, mouse[1] - HEIGHT // 2)
    return True


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    camera_group = CameraGroup()
    player = Player((640, 360), camera_group)
    player2 = Player((840, 460), camera_group)
    for i in range(20):
        random_x = randint(1000, 2000)
        random_y = randint(1000, 2000)
        Tree((random_x, random_y), camera_group)
    camera_group.custom_draw(player)
    camera_group.custom_draw(player2)

    running = True
    while running:
        running = events(player)
        player.update()
        screen.fill("#71ddee")
        camera_group.update()
        camera_group.custom_draw(player)
        pg.display.update()
        clock.tick(FPS)



    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
