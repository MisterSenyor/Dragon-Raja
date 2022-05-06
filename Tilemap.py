import pygame as pg
import pytmx
from settings import *


class Map:
    def __init__(self, filename):
        self.data = []
        with open(filename, 'rt') as f:
            for line in f:
                self.data.append(line.strip())

        self.tilewidth = len(self.data[0])
        self.tileheight = len(self.data)
        self.width = self.tilewidth * TILESIZE
        self.height = self.tileheight * TILESIZE

class TiledMap:
    def __init__(self, filename):
        tm = pytmx.TiledMap(filename, pixelalpha=True)
        self.filename = filename
        self.width = tm.width * TILESIZE
        self.height = tm.height * TILESIZE
        self.tmxdata = tm

    def render(self, surface):
        tm = pytmx.load_pygame(self.filename, pixelalpha=True)
        ti = tm.get_tile_image_by_gid
        for layer in tm.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid, in layer:
                    tile = ti(gid)
                    if tile:
                        tile = pg.transform.scale(tile, (TILESIZE, TILESIZE))
                        surface.blit(tile, (x * TILESIZE,
                                            y * TILESIZE))
    
    def draw(self, surface, camera):
        rect = camera.apply_rect(self.rect)
        for i in range(MAP_COEFFICIENT):
            for j in range(MAP_COEFFICIENT):
                surface.blit(self.image, rect.move(i * self.width, j * self.height))

    def make_map(self):
        temp_surface = pg.Surface((self.width, self.height))
        self.render(temp_surface)
        self.get_objects(apply_func=lambda x: x)
        self.image = temp_surface
        self.rect = temp_surface.get_rect()
        return temp_surface
    
    def get_objects(self, apply_func=lambda x: pg.Rect(x[0], x[1])) -> list:
        walls = []
        for tile in self.tmxdata.objects:
            if tile.name == 'w':
                for i in range(MAP_COEFFICIENT):
                    for j in range(MAP_COEFFICIENT):
                        walls.append(apply_func(((tile.x + i * self.width, tile.y + j * self.height), (tile.width, tile.height))))
        
        return walls

class Camera:
    def __init__(self, width, height):
        self.camera = pg.Rect(0, 0, width, height)
        self.width = width
        self.height = height

    def apply(self, entity):
        return entity.rect.move(self.camera.topleft)

    def apply_rect(self, rect):
        return rect.move(self.camera.topleft)

    def update(self, target):
        x = -target.rect.x + int(WIDTH / 2)
        y = -target.rect.y + int(HEIGHT / 2)
        

        # limit scrolling to map size
        x = min(0, x)  # left
        y = min(0, y)  # top
        x = max(-(self.width - WIDTH), x)  # right
        y = max(-(self.height - HEIGHT), y)  # bottom
        self.camera = pg.Rect(x, y, self.width, self.height)
