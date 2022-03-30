import logging
import sys
import threading
from os import path
from random import randint, choice

from Tilemap import *
from animated_sprite import *
from entities import *
from client_chat import chat_client

pg.init()


class Button(pg.sprite.Sprite):
    def __init__(self, groups, pos, size, font_size, text, target, args):
        self.groups = groups
        pg.sprite.Sprite.__init__(self, groups)
        self.rect = pg.Rect(pos, size)
        self.image = pg.Surface(size)
        self.font_size = font_size
        self.active = False
        self.text = text
        self.target = target
        self.args = args
        self.color = (150, 150, 150)

    def events(self, event_list):
        for event in event_list:
            if event.type == pg.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos):
                    self.target(self.args)

    def update(self, *args, **kwargs):
        mouse = pg.mouse.get_pos()
        if self.rect.colliedepoint(mouse):
            self.color = (90, 90, 90)
        else:
            self.color = (150, 150, 150)

    def draw(self, screen):
        pg.draw.rect(screen, self.color, self.rect)


class loginScreen(pg.sprite.Sprite):
    def __init__(self, groups, image, height, width):
        self.groups = groups
        pg.sprite.Sprite.__init__(self, groups)
        self.image = image
        self.size = (width,height)
        self.active = False

class TextInputBox(pg.sprite.Sprite):
    def __init__(self, groups, pos, size, font_size):
        self.groups = groups
        pg.sprite.Sprite.__init__(self, groups)
        self.rect = pg.Rect(pos, size)
        self.image = pg.Surface(size)
        self.font_size = font_size
        self.active = False
        self.text = ""

    def events(self, event_list):
        for event in event_list:
            if event.type == pg.MOUSEBUTTONDOWN:
                self.active = self.rect.collidepoint(event.pos)
            if event.type == pg.KEYDOWN and self.active:
                if event.key == pg.K_RETURN:
                    self.active = False
                elif event.key == pg.K_BACKSPACE:
                    self.text = self.text[:-1]
                else:
                    self.text += event.unicode

    def update(self, *args, **kwargs):
        pass

    def draw(self, screen):
        pg.draw.rect(screen, (40, 40, 40), self.rect)
        font = pygame.font.SysFont('./graphics/fonts/comicsans.ttf', self.font_size)
        img = font.render(self.text, True, BLACK)
        screen.blit(img, self.rect)


def login_events(text, button):
    all_events = pg.event.get()
    for event in all_events:
        if event.type == pg.QUIT:
            return False
    for t in text:
        t.events(all_events)
    for b in button:
        b.events(all_events)
    return True

def login_update():
    pass

def sign_up():
    pass

def log_in():
    pass


def login_draw(screen, text):
    for t in text:
            t.draw(screen)
    pg.display.update()


def drop_item(player, inv: Inventory, sprite_groups):
    """ DROPS ITEM FROM CURRENT SLOT ON THE GROUND"""
    # GET CUR ITEM:
    item = inv.slots[inv.cur_slot]

    # CHECK IF CUR SLOT IS EMPTY:
    if item != 0:
        # REMOVE FROM INVENTORY
        inv.remove_item(inv.cur_slot)

        # CHECK IN WHICH DIRECTION TO DROP ITEM:
        if player.direction == 1:
            pos = player.rect.topleft
        else:
            pos = player.rect.topright
        dropped_item = Dropped(item.item_type, pos,  [sprite_groups["all"], sprite_groups["dropped"]])


def pick_item(player, inv: Inventory, sprite_groups):
    """" PICKS UP ITEM:
    CHECKS IF INVENTORY IS FULL,
    CHECKS COLLISION WITH DROPPED ITEMS,
    REMOVES DROPPED ITEM FROM ITS GROUPS AND ADDS ITEM TO INVENTORY"""

    # CHECK INV:
    if inv.is_full():
        print("INV FULL")
        return

    # GO OVER ALL DROPPED ITEMS:
    for sprite in sprite_groups["dropped"]:
        # CHECK COLLISION WITH PLAYER:
        if pg.sprite.collide_rect(player, sprite):
            # ADD ITEM TO INV AND PLAYER ITEMS:
            item = Item(sprite.item_type, player)
            inv.add_item(item)
            player.items.add(item)

            # REMOVE DROPPED ITEM FROM SPRITE GROUPS:
            sprite.remove(sprite_groups["all"], sprite_groups["dropped"])


def update_dir(player: Entity, camera):
    """ UPDATES PLAYER DIRECTION ACCORDING TO
    MOUSE POS (0 = RIGHT, 1 = LEFT) """
    mouse = pg.mouse.get_pos()
    if mouse[0] >= camera.apply(player).topleft[0]:
        player.direction = 0
    else:
        player.direction = 1


def handle_keyboard(player, inv, camera, key, chat, sprite_groups):
    if key == 120:  # X KEY
        update_dir(player, camera)
        player.melee_attack()

    elif key == 122:  # Z key
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, pg.mouse.get_pos()[1] - HEIGHT // 2)
        axe = Projectile("axe", player, vect, [sprite_groups["all"], sprite_groups["projectiles"]])

        update_dir(player, camera)

    elif key == 99:  # C KEY
        # GET VECTOR FOR PROJECTILE:
        vect = pg.math.Vector2(pg.mouse.get_pos()[0] - WIDTH // 2, pg.mouse.get_pos()[1] - HEIGHT // 2)
        arrow = Projectile("arrow", player, vect, [sprite_groups["all"], sprite_groups["projectiles"]])

        update_dir(player, camera)

    elif key == 114:  # R KEY
        item = inv.slots[inv.cur_slot]
        # CHECK IF EMPTY SLOT
        if item != 0:
            # USE ITEM:
            item.use_item()
            inv.remove_item(inv.cur_slot)

    elif key == 103:  # G KEY
        player.use_skill(1, sprite_groups, inv)

    elif key == 113:  # Q KEY
        drop_item(player, inv, sprite_groups)

    elif key == 98:
        pick_item(player, inv, sprite_groups)

    elif key == 116:  # T KEY - CHAT
        chat.is_pressed = True


def handle_chat(chat, key):
    if key == 27:  # ESCAPE
        chat.cur_typed = ''
        chat.is_pressed = False
        return
    elif key == 8 or key == 127:  # BACKSPACE OR DELETE
        chat.cur_typed = chat.cur_typed[:-1]
        return
    elif key == 13:  # ENTER
        chat.send_line(chat.cur_typed)
        chat.cur_typed = ''
        chat.is_pressed = False
    else:
        # CHECK IF MAX CHAR LIM REACHED:
        if len(chat.cur_typed) < chat._char_lim:
            try:
                # ADD NEW LETTER TO TYPED LINE
                chat.cur_typed += chr(key)
            except ValueError:
                logging.error('exception while converting from ascii')


def handle_mouse(player, event, inv, camera):
    # CHECK LEFT CLICK:
    if event.button == 1:
        # UPDATE DIRECTION:
        update_dir(player, camera)

        # MOVE THE PLAYER ACCORDING TO MOUSE POS
        mouse = pg.mouse.get_pos()
        player.move(player.rect.centerx + mouse[0] - camera.apply(player).topleft[0],
                    player.rect.centery + mouse[1] - camera.apply(player).topleft[1])
        return

    # CHECK MOUSE SCROLL WHEEL:
    if event.button > 3:
        if event.button % 2 == 0 and inv.cur_slot < 14:  # SCROLL UP
            inv.cur_slot += 1
        else:  # SCROLL DOWN
            if inv.cur_slot > 0:
                inv.cur_slot -= 1
        return


def events(player, inv, camera, chat, sprite_groups, text):
    all_events = pg.event.get()
    for t in text:
        t.events(all_events)
    for event in all_events:
        if event.type == pg.QUIT:
            return False
        if chat.is_pressed:
            if event.type == pg.KEYDOWN:
                handle_chat(chat, event.key)
            return True
        if event.type == pg.KEYDOWN:
            handle_keyboard(player, inv, camera, event.key, chat, sprite_groups)
        if event.type == pg.MOUSEBUTTONDOWN:
            handle_mouse(player, event, inv, camera)
    return True


def update(all_sprites, player, camera, map_rect, sprite_groups):
    for sprite in sprite_groups['all']:
        sprite.update(map_rect, sprite_groups)
        sprite.update(map_rect, sprite_groups)

    camera.update(player)


def draw(screen, all_sprites, map_img, map_rect, inv, chat, camera, text):
    screen.fill(BGCOLOR)

    screen.blit(map_img, camera.apply_rect(map_rect))

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite))
        sprite.draw(screen, camera)
    inv.render(screen)  # RENDER INVENTORY
    chat.update(screen)

    for t in text:
        t.draw(screen)
    pg.display.update()


def create_enemies(sprite_groups, mob_anims):
    return
    mobs = []
    for i in range(0, 100):
        mobs.append(
            Mob((randint(0, 12000), randint(0, 7600)), [sprite_groups["all"], sprite_groups["entity"]],
                choice(mob_anims), 2, 15))


def run():
    logging.basicConfig(level=logging.DEBUG)

    clock = pg.time.Clock()
    screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
    WIDTH, HEIGHT = screen.get_size()

    all_sprites = pg.sprite.Group()
    entity_sprites = pg.sprite.Group()
    players_sprites = pg.sprite.Group()
    projectile_sprites = pg.sprite.Group()
    dropped_sprites = pg.sprite.Group()
    sprite_groups = {
        "all": all_sprites,
        "entity": entity_sprites,
        "players": players_sprites,
        "projectiles": projectile_sprites,
        "dropped": dropped_sprites
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
    sock_client = client.Client(sock=sock, server=(SERVER_IP, SERVER_PORT), sprite_groups=sprite_groups,
                                player_animations=player_anims, mob_animations=mob_anims[0], player_anim_speed=5,
                                player_walk_speed=5, mob_anim_speed=15, mob_walk_speed=2)
    sock_client.init()
    threading.Thread(target=sock_client.receive_updates).start()
    username = "moshe"

    client_chat = chat_client(username)
    client_chat.start()
    chat = Chat(client_chat)
    threading.Thread(target=client_chat.receive, args=(chat,)).start()

    player = sock_client.main_player
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
    inv = Inventory((WIDTH, HEIGHT))

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

    player.items.add(speed_pot)

    inv.add_item(speed_pot)

    state = 'LOGIN'
    text_boxes = [TextInputBox([], (555, 305), (420, 55), 45),
                  TextInputBox([], (555, 475), (420, 55), 45)]
    buttons = [Button([], (825, 610), (133, 55), 0, "", 0, 0),
               Button([], (575, 610), (133, 55), 0, "", 0, 0)]

    drp_pot = Dropped("speed_pot", player.rect.center, [sprite_groups["all"], sprite_groups["dropped"]])
    while running:
        if state == 'GAME':
            running = events(player, inv, camera, chat, sprite_groups, text_boxes)
            update(all_sprites, player, camera, map_rect, sprite_groups)
            draw(screen, sprite_groups["all"], map_img, map_rect, inv, chat, camera, text_boxes)

        elif state == 'LOGIN':
            login = loginScreen([], "login_screen.png", 602, 529)
            img = pg.image.load(login.image)
            screen.blit(img, (500, 140))
            pg.display.flip()
            sock_lb = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            port_lb = 3333
            sock_lb.bind((IP, port_lb))
            finish = True
            while finish:
                finish = login_events(text_boxes, buttons)
                login_draw(screen, text_boxes)
                login_draw(screen, buttons)
                clock.tick(FPS)

        clock.tick(FPS)

    sock_client.send_update('disconnect', {'id': player.id})

    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
    quit()
