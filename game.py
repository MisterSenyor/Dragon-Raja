import pygame as pg

from settings import *

pg.init()
WIDTH, HEIGHT = 1000, 700


class Player(pg.sprite.Sprite):
    def __init__(self, x, y):
        super(Player, self).__init__()
        self.walk_speed = 5
        self._start, self._end = (0, 0), (0, 0)
        self.pos = x, y
        self._i = 0
        self._t = 1

        self.image = pg.Surface((TILESIZE, TILESIZE))
        self.image.fill((255, 0, 0))

    def move(self, x, y):
        self._start = self.pos
        self._end = x, y
        dist = ((self._end[0] - self._start[0]) ** 2 + (self._end[1] - self._start[1]) ** 2) ** 0.5
        self._t = dist / self.walk_speed
        self._i = 0

    def update(self):
        """" UPDATES PLAYER LOCATION:
        for each iteration update pos by averaging the 'start' and 'end' for each axis
        """
        # TODO: check dt
        if self._i < self._t:
            self.pos = (round(self._start[0] + (self._end[0] - self._start[0]) * self._i / self._t),
                        round(self._start[1] + (self._end[1] - self._start[1]) * self._i / self._t))
            self._i += 1


def update(player):
    player.update()


def draw(screen, player):
    screen.fill((0, 255, 0))
    screen.blit(player.image, player.pos)
    pg.display.flip()


def events(player):
    for event in pg.event.get():
        if event.type == pg.QUIT:
            return False
        if event.type == pg.MOUSEBUTTONDOWN:
            player.move(*pg.mouse.get_pos())
    return True


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    player = Player(4, 4)
    running = True
    while running:
        running = events(player)
        update(player)
        draw(screen, player)
        clock.tick(FPS)
    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
