import pygame as pg
from settings import *

pg.init()
WIDTH, HEIGHT = 1000, 700

class Player(pg.sprite.Sprite):
    def __init__(self, x, y):
        self.WALK_SPEED = 1
        self.x = x
        self.y = y
        self.target = (self.x, self.y)
        self.image = pg.Surface((TILESIZE, TILESIZE))
        self.image.fill((255, 0, 0))


    def move(self, x, y):
        self.target = (x, y)

    def update(self):
        if self.target[0] != self.x:
            self.x += ((self.x > self.target[0]) * -2 + 1) * self.WALK_SPEED
        if self.target[1] != self.y:
            self.y += ((self.y > self.target[1]) * -2 + 1) * self.WALK_SPEED


def update(player):
    player.update()

def draw(screen, player):
    screen.fill((0, 255, 0))
    screen.blit(player.image, (player.x, player.y))
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
