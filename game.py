import random
import threading
from os import path
from random import randint, randrange, choice

import client
from Tilemap import *
from animated_sprite import *
from entities import *

pg.init()


def update_dir(player: Entity, camera):
    """ UPDATES PLAYER DIRECTION ACCORDING TO
    MOUSE POS (0 = RIGHT, 1 = LEFT) """
    mouse = pg.mouse.get_pos()
    if mouse[0] >= camera.apply(player).topleft[0]:
        player.direction = 0
    else:
        player.direction = 1


def handle_keyboard(player, inv, camera, key):
    if key == 120:  # X KEY
        update_dir(player, camera)
        player.melee_attack()

    elif key == 122:  # Z key
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, HEIGHT // 2 - pg.mouse.get_pos()[1])
        axe = Projectile("axe", player, vect, player.groups)
        update_dir(player, camera)

    elif key == 99:  # C KEY
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, HEIGHT // 2 - pg.mouse.get_pos()[1])
        arrow = Projectile("arrow", player, vect, player.groups)
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


def events(player, inv, camera):
    for event in pg.event.get():
        if event.type == pg.QUIT:
            return False
        if event.type == pg.KEYDOWN:
            handle_keyboard(player, inv, camera, event.key)
        if event.type == pg.MOUSEBUTTONDOWN:
            handle_mouse(player, event, inv, camera)
    return True


def update(all_sprites, player, camera, map_rect):
    for sprite in all_sprites:
        sprite.update(map_rect)

    camera.update(player)


def draw(screen, all_sprites, map_img, map_rect, inv, camera):
    screen.fill(BGCOLOR)

    screen.blit(map_img, camera.apply_rect(map_rect))

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite))
        sprite.draw(screen, camera)
    inv.render(screen)  # RENDER INVENTORY
    pg.display.update()


def create_enemies(all_sprites, mob_anims):
    mobs = []
    for i in range(0, 100):
        mobs.append(
            Entity((randint(0, 12000), randint(0, 7600)), all_sprites, choice(mob_anims), 2, 15, auto_move=True))


def run():
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    all_sprites = pg.sprite.Group()
    entity_sprites = pg.sprite.Group()
    projectile_sprites = pg.sprite.Group()
    all_sprite_groups = [all_sprites, entity_sprites, projectile_sprites]

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

    player = Entity((1400, 1360), all_sprite_groups, player_anims, 5, 5)
    mob = Entity((1600, 1390), all_sprite_groups, choice(mob_anims), 2, 15, auto_move=True)
    create_enemies(all_sprite_groups, mob_anims)

    player2 = Entity((1200, 1300), all_sprite_groups, player_anims, 5, 5)
    print(player2.id)
    player2.move(100, 100)
    # SETTING UP CLIENT

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((IP, PORT))
    game_client = client.Client(sock=sock, server=(SERVER_IP, SERVER_PORT))
    threading.Thread(target=game_client.receive_updates, args=(entity_sprites,)).start()

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

    player.health = 50
    while running:
        running = events(player, inv, camera)
        update(all_sprite_groups[0], player, camera, map_rect)  # all_sprite_groups[0] : all_sprites
        draw(screen, all_sprite_groups[0], map_img, map_rect, inv, camera)
        clock.tick(FPS)

    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
