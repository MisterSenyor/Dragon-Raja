import pygame


class AnimatedSprite(pygame.sprite.Sprite):
    def __init__(self, path: str, count: int, is_single_file:bool):
        super(AnimatedSprite, self).__init__()
        if is_single_file:
            self._surface_image = pygame.image.load(path).convert()
        else:
            self._surface_image = pygame.image.load(path+"1.png")
        self._surface_image.set_colorkey((113, 102, 79))
        width = self._surface_image.get_width() / count
        if is_single_file:
            self.surfaces = [self._surface_image.subsurface([i * width, 0, width, self._surface_image.get_height()]) for i
                    in range(count)]
         
        else:
            for i in range(count):
                print(path + f"{i + 1}.png")
            self.surfaces = [pygame.image.load(path + f"{i + 1}.png") for i in range(count)]
        self.surface_index = 0
        self.image = self.surfaces[self.surface_index]

    def update(self, *args, **kwargs) -> None:
        self.surface_index = (self.surface_index + 1) % len(self.surfaces)
        self.image = self.surfaces[self.surface_index]
