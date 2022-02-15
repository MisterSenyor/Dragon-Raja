import pygame


class AnimatedSprite(pygame.sprite.Sprite):
    def __init__(self, path: str, count: int):
        super(AnimatedSprite, self).__init__()
        self._surface_image = pygame.image.load(path)
        width = self._surface_image.get_width() / count
        self.surfaces = [self._surface_image.subsurface([i * width, 0, width, self._surface_image.get_height()]) for i
                         in range(count)]
        self.surface_index = 0
        self.image = self.surfaces[self.surface_index]

    def update(self, *args, **kwargs) -> None:
        self.surface_index = (self.surface_index + 1) % len(self.surfaces)
        self.image = self.surfaces[self.surface_index]
