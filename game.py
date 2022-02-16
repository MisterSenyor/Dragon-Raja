import pygame as pg
from animated_sprite import AnimatedSprite

from settings import *

pg.init()
WIDTH, HEIGHT = 1280, 720



class Player(pg.sprite.Sprite):
    def __init__(self, pos, camera_group):
        super().__init__(camera_group)
        self.camera_group =  camera_group
        super(Player, self).__init__()
        self.walk_speed = 5
        self._start, self._end = (0, 0), (0, 0)
        self.pos = pos
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
        self.rect = self.image.get_rect(topleft=self.pos)
        self.image.fill((255, 0, 0))

    def move(self, x, y):
        self.change_status('run')
        self._start = self.pos
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
        if self.status == 'run':
            if self._i < self._t:
                # UPDATE POS:
                self.pos = (round(self._start[0] + (self._end[0] - self._start[0]) * self._i / self._t),
                            round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t))
                self.camera_group.offset = pg.Vector2(self.pos)
                self._i += 1
                # UPDATE CAMERA:
                self.rect = self.image.get_rect(topleft=self.pos)
            else:
                self.pos = self._end
                self.change_status('idle')
        self.animation.update()
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
        for sprite in self.sprites():
            self.display_surface.blit(sprite.image, (self.half_w, self.half_h))




    def center_target_camera(self, target):
        self.offset.x = target.rect.centerx - self.half_w
        self.offset.y = target.rect.centery - self.half_h


def events(player):
    for event in pg.event.get():
        if event.type == pg.QUIT:
            return False
        if event.type == pg.MOUSEBUTTONDOWN:
            mouse = pg.mouse.get_pos()
            player.move(mouse[0] - WIDTH // 2, mouse[1] - HEIGHT // 2)
    return True


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    camera_group = CameraGroup()
    player = Player((640, 360), camera_group)
    camera_group.custom_draw(player)

    running = True
    while running:
        running = events(player)
        player.update()
        screen.fill("#964B00")
        camera_group.update()
        camera_group.custom_draw(player)
        pg.display.update()
        clock.tick(FPS)

    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
