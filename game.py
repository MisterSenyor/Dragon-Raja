import random
import threading
from os import path
from random import randint, randrange, choice
import sys
import client
from Tilemap import *
from animated_sprite import *
from entities import *

pg.init()

class MainPlayer(Entity):
    def __init__(self, sock_client: 'client.Client', *args, **kwargs):
        super(MainPlayer, self).__init__(*args, **kwargs)
        self.client = sock_client

    def move(self, x, y, send_update=True):
        super(MainPlayer, self).move(x, y)
        if send_update:
            self.client.send_update('move', {'id': self.id, 'pos': [x, y]})

    def melee_attack(self, send_update=True):
        super(MainPlayer, self).melee_attack()
        if send_update:
            self.client.send_update('attack', {'id': self.id})
            
def update_dir(player: Entity, camera):
    """ UPDATES PLAYER DIRECTION ACCORDING TO
    MOUSE POS (0 = RIGHT, 1 = LEFT) """
    mouse = pg.mouse.get_pos()
    if mouse[0] >= camera.apply(player).topleft[0]:
        player.direction = 0
    else:
        player.direction = 1


def handle_keyboard(player, inv, camera, key, all_sprites, projectile_sprites):
    if key == 120:  # X KEY
        update_dir(player, camera)
        player.melee_attack()

    elif key == 122:  # Z key
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, HEIGHT // 2 - pg.mouse.get_pos()[1])
        axe = Projectile("axe", player, vect, [all_sprites, projectile_sprites])
        update_dir(player, camera)

    elif key == 99:  # C KEY
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, HEIGHT // 2 - pg.mouse.get_pos()[1])
        arrow = Projectile("arrow", player, vect, [all_sprites, projectile_sprites])
        update_dir(player, camera)

    elif key == 114:  # R KEY
        item = inv.slots[inv.cur_slot]
        # CHECK IF EMPTY SLOT
        if item != 0:
            # USE ITEM:
            item.use_item()
            inv.remove_item(inv.cur_slot)


def handle_mouse(player, event, inv, camera):
    # CHECK LEFT CLICK:
    if event.button == 1:
        # UPDATE DIRECTION:
        update_dir(player, camera)

        # MOVE THE PLAYER ACCORDING TO MOUSE POS
        mouse = pg.mouse.get_pos()
        player.move(mouse[0] - camera.apply(player).topleft[0],
                    mouse[1] - camera.apply(player).topleft[1])
        return

    # CHECK MOUSE SCROLL WHEEL:
    if event.button > 3:
        if event.button % 2 == 0 and inv.cur_slot < 14:  # SCROLL UP
            inv.cur_slot += 1
        else:  # SCROLL DOWN
            if inv.cur_slot > 0:
                inv.cur_slot -= 1
        return


def events(player, inv, camera, all_sprites):
    for event in pg.event.get():
        if event.type == pg.QUIT:
            return False
        if event.type == pg.KEYDOWN:
            handle_keyboard(player, inv, camera, event.key, all_sprites, projectile_sprites)
        if event.type == pg.MOUSEBUTTONDOWN:
            handle_mouse(player, event, inv, camera)
    return True


def update(all_sprites, player, camera, map_rect, players):
    for sprite in all_sprites:
        sprite.update(map_rect, players, camera, all_sprites)

    camera.update(player)


def draw(screen, all_sprites, map_img, map_rect, inv, camera):
    screen.fill(BGCOLOR)

    screen.blit(map_img, camera.apply_rect(map_rect))

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite))
        sprite.draw(screen, camera)
    inv.render(screen)  # RENDER INVENTORY
    pg.display.update()


def create_enemies(sprite_groups, mob_anims):
    mobs = []
    for i in range(0, 100):
        mobs.append(
            Mob((randint(0, 12000), randint(0, 7600)), sprite_groups["all"], choice(mob_anims), 2, 15))


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    all_sprites = pg.sprite.Group()
    entity_sprites = pg.sprite.Group()
    players_sprites = pg.sprite.Group()
    projectile_sprites = pg.sprite.Group()
    sprite_groups = {
        "all": all_sprites,
        "entity": entity_sprites,
        "players": players_sprites,
        "projectiles": projectile_sprites
    }

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

    # SETTING UP CLIENT

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = PORT if len(sys.argv) == 1 else int(sys.argv[1])
    sock.bind((IP, port))
    sock_client = client.Client(sock=sock, server=(SERVER_IP, SERVER_PORT), all_sprite_groups=all_sprite_groups,
                                player_animations=player_anims, player_anim_speed=5)
    threading.Thread(target=sock_client.receive_updates).start()

    player = MainPlayer(sock_client, (1400, 1360), sprite_groups, player_anims, 5, 5)
    mob = Entity((1600, 1390), sprite_groups, choice(mob_anims), 2, 15, auto_move=True)
    create_enemies(sprite_groups, mob_anims)

    # SETTING UP MAP

    map_folder = 'maps'

    tiled_map = TiledMap(path.join(map_folder, 'map_new.tmx'))
    map_img = tiled_map.make_map()
    map_rect = map_img.get_rect()

    # SETTING UP CAMERA

    camera = Camera(tiled_map.width, tiled_map.height)
    pg.mouse.set_cursor(pg.cursors.broken_x)

    running = True
    inv = Inventory()

    # ITEMS:
    speed_pot = Item("speed_pot", player)
    strength_pot = Item("strength_pot", player)
    heal_pot = Item("heal_pot", player)
    useless_card = Item("useless_card", player)

    # RANDOM INVENTORY FOR TESTING
    player.items.add(strength_pot)
    inv.add_item(strength_pot)
    player.items.add(strength_pot)
    inv.add_item(strength_pot)
    player.items.add(strength_pot)
    inv.add_item(strength_pot)
    player.items.add(strength_pot)
    inv.add_item(strength_pot)
    player.items.add(heal_pot)
    inv.add_item(heal_pot)
    player.items.add(speed_pot)
    inv.add_item(speed_pot)

    player.items.add(speed_pot)
    inv.add_item(speed_pot)

    player.items.add(speed_pot)
    inv.add_item(speed_pot)

    sock_client.send_update('connect', {
        'entity': {'id': player.id, 'pos': player.rect.topleft, 'walk_speed': player.walk_speed,
                   'items': [{'id': item.id, 'type': item.item_type} for item in player.items]}})

    player.health = 50
    while running:
        running = events(player, inv, camera, sprite_groups)
        update(all_sprites, player, camera, map_rect, sprite_groups)
        draw(screen, sprite_groups["all"], map_img, map_rect, inv, camera)
        clock.tick(FPS)

    sock_client.send_update('disconnect', {'id': player.id})

    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
    quit()
