from os import path

from typing import Optional
import client
import new_client
from Tilemap import *
from animated_sprite import *
from entities import *

from client_chat import *

pg.init()


class Button(pg.sprite.Sprite):
    def __init__(self, groups, pos, size):
        self.groups = groups
        pg.sprite.Sprite.__init__(self, *groups)
        self.rect = pg.Rect(pos, size)
        self.clicked = False

    def events(self, event_list):
        """ EVENTS IN BUTTON
        """

        for event in event_list:
            if event.type == pg.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos):
                    self.clicked = True
                    return
        self.clicked = False


class TextInputBox(pg.sprite.Sprite):
    def __init__(self, groups, pos, size, font_size):
        self.groups = groups
        pg.sprite.Sprite.__init__(self, *groups)
        self.rect = pg.Rect(pos, size)
        self.font_size = font_size
        self.active = False
        self.text = ""

    def events(self, event_list):
        for event in event_list:
            if event.type == pg.MOUSEBUTTONDOWN:
                # CHECK MOUSE COLLISION WITH BUTTON
                self.active = self.rect.collidepoint(event.pos)
            if event.type == pg.KEYDOWN and self.active:
                if event.key == pg.K_RETURN:
                    self.active = False
                elif event.key == pg.K_BACKSPACE or event.key == pg.K_DELETE:
                    # REMOVE LAST CHAR FROM TEXT
                    self.text = self.text[:-1]
                else:
                    # CHECK USERNAME CHARACTER LIMIT
                    if len(self.text) <= username_lim:
                        self.text += event.unicode

    def draw(self, screen):
        """ DRAWS TEXT FROM TEXT BOX"""
        font = pygame.font.SysFont('./graphics/fonts/comicsans.ttf', self.font_size)
        img = font.render(self.text, True, BLACK)
        screen.blit(img, self.rect)


def login_events(textbox_dict: Dict[str, TextInputBox], button_dict: Dict[str, Button]) -> Optional[str]:
    """ CHECK EVENTS IN LOGIN SCREEN,
    RETURNS THE ACTION THE USER HAS DONE"""

    all_events = pg.event.get()
    for event in all_events:
        if event.type == pg.QUIT:
            return 'quit'
    for textbox in textbox_dict.values():
        textbox.events(all_events)
    for button_name, button in button_dict.items():
        button.events(all_events)
        if button.clicked:
            if button_name == 'login_button':
                return 'login'
            if button_name == 'sign_up_button':
                return 'sign_up'
    return None


def login_draw(screen, textbox_dict: Dict[str, TextInputBox]):
    """ DRAWS TEXT FROM TEXT BOXES ONTO SCREEN,
     UPDATES SCREEN """

    for t in textbox_dict.values():
        t.draw(screen)
    pg.display.update()


def update_dir(player: Entity, camera):
    """ UPDATES PLAYER DIRECTION ACCORDING TO
    MOUSE POS (0 = RIGHT, 1 = LEFT) """
    mouse = pg.mouse.get_pos()
    if mouse[0] >= camera.apply(player).topleft[0]:
        player.direction = 0
    else:
        player.direction = 1


def handle_keyboard(player: MainPlayer, inv, camera, key, chat, sprite_groups):
    if key == 122:  # Z key
        inv.switch_weapon()
        
    elif key == 114:  # R KEY
        player.use_item(inv, sprite_groups)

    elif key == 103:  # G KEY
        player.send_use_skill(1)

    elif key == 104:  # H KEY
        player.send_use_skill(2)

    elif key == 106:  # J KEY
        player.send_use_skill(3)

    elif key == 113:  # Q KEY
        player.drop_item(inv, sprite_groups)

    elif key == 98:  # B KEY
        player.pick_item(inv, sprite_groups)

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
        if len(chat.cur_typed) < char_lim:
            try:
                # ADD NEW LETTER TO TYPED LINE
                chat.cur_typed += chr(key)
            except ValueError:
                logging.error('exception while converting from ascii')


def handle_mouse(player, event, inv, camera, sprite_groups):
    # CHECK LEFT CLICK:
    if event.button == 1:
        # UPDATE DIRECTION:
        update_dir(player, camera)

        # MOVE THE PLAYER ACCORDING TO MOUSE POS
        mouse = pg.mouse.get_pos()
        player.move(player.rect.centerx + mouse[0] - camera.apply(player).topleft[0],
                    player.rect.centery + mouse[1] - camera.apply(player).topleft[1])
   
    elif event.button == 3:
        update_dir(player, camera)
        if inv.weapons[inv.weapon_held] == 'sword':
            player.melee_attack()
        else:
            player.projectile_attack(inv.weapons[inv.weapon_held])

    # CHECK MOUSE SCROLL WHEEL:
    elif event.button > 3:
        if event.button % 2 == 0 and inv.cur_slot < 14:  # SCROLL UP
            inv.cur_slot += 1
        else:  # SCROLL DOWN
            if inv.cur_slot > 0:
                inv.cur_slot -= 1


def events(player, inv, camera, chat, sprite_groups):
    all_events = pg.event.get()
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
            handle_mouse(player, event, inv, camera, sprite_groups)
    return True


def update(all_sprites, player, camera, map_rect, sprite_groups):
    for sprite in sprite_groups['all']:
        sprite.update(map_rect, sprite_groups)

    camera.update(player)


def draw(screen, all_sprites, map_img, map_rect, inv, chat, camera):
    screen.fill(BGCOLOR)

    screen.blit(map_img, camera.apply_rect(map_rect))

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite))
        sprite.draw(screen, camera)
    inv.render(screen)  # RENDER INVENTORY
    chat.update(screen)

    pg.display.update()


def login_state(screen, clock):
    """ LOGIN STATE MAIN LOOP FUNCTION:
    RETURNS ACTION, USERNAME, PASSWORD
    ACTION IS EITHER 'login' OR 'sign_up'
    """

    # SET UP TEXT BOXES:
    text_boxes = {
        'username_textbox': TextInputBox((), (555, 305), (420, 55), 45),
        'password_textbox': TextInputBox((), (555, 475), (420, 55), 45)
    }
    buttons = {
        'sign_up_button': Button((), (825, 610), (133, 55)),
        'login_button': Button((), (575, 610), (133, 55))
    }

    # SETUP LOGIN SCREEN:
    img = pg.image.load("login_screen.png")
    screen.blit(img, (500, 140))
    pg.display.flip()

    action = None
    while action is None:
        # CHECK EVENTS:
        action = login_events(text_boxes, buttons)
        if action == 'quit':
            pg.quit()
            quit()
        # DRAW TEXT:
        login_draw(screen, text_boxes)
        # REDRAW BACKGROUND:
        screen.blit(img, (500, 140))
        clock.tick(FPS)

    username = text_boxes['username_textbox'].text
    password = text_boxes['password_textbox'].text
    pg.event.clear()
    return action, username, password


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
    if ENABLE_SHADOWS:
        sprite_groups['shadows'] = pg.sprite.Group()

    player_anims = {
        'idle': AnimatedSprite('graphics/Knight/KnightIdle_strip.png', 15, True),
        'run': AnimatedSprite('graphics/Knight/KnightRun_strip.png', 8, True),
        'death': AnimatedSprite('graphics/Knight/KnightDeath_strip.png', 15, True),
        'attack': AnimatedSprite('graphics/Knight/KnightAttack_strip.png', 22, True)
    }
    mob_anims = {
        'dragon': {
            'idle': AnimatedSprite('graphics/small_dragon/Idle', 3, False),
            'run': AnimatedSprite('graphics/small_dragon/Walk', 4, False),
            'death': AnimatedSprite('graphics/Knight/KnightDeath_strip.png', 15, True)
        },
        'demon': {
            'idle': AnimatedSprite('graphics/demon_axe_red/ready_', 6, False),
            'run': AnimatedSprite('graphics/demon_axe_red/run_', 6, False),
            'death': AnimatedSprite('graphics/demon_axe_red/dead_', 4, False),
            'attack': AnimatedSprite('graphics/demon_axe_red/attack1_', 6, False), 
        }
    }

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

    action, username, password = login_state(screen, clock)

    # SETTING UP CLIENT:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if MULTIPLE_SERVERS:
        sock_client = new_client.NewClient(sock=sock, server=(SERVER_IP, SERVER_PORT), sprite_groups=sprite_groups,
                                           player_animations=player_anims, mob_animations=mob_anims,
                                           player_anim_speed=5, player_walk_speed=5, mob_anim_speed=15,
                                           mob_walk_speed=2, lb_address=LB_ADDRESS)

        message = sock_client.connect(username=username, password=password, action=action)
        while message is not None:
            logging.info(f'client connection failed: {message=}, {username=}, {password=}')
            action, username, password = login_state(screen, clock)
            message = sock_client.connect(username=username, password=password, action=action)
    else:
        sock_client = client.Client(sock=sock, server=(SERVER_IP, SERVER_PORT), sprite_groups=sprite_groups,
                                    player_animations=player_anims, mob_animations=mob_anims,
                                    player_anim_speed=5, player_walk_speed=5, mob_anim_speed=15,
                                    mob_walk_speed=2)
        sock_client.connect(username=username)

    sock_thread = threading.Thread(target=sock_client.receive_updates, daemon=True)
    sock_thread.start()

    player = sock_client.main_player
    for item in player.items:
        inv.add_item(item)

    # CHAT:
    client_chat = ChatClient(username)
    client_chat.start()
    chat = Chat(client_chat, username=username)
    chat_thread = threading.Thread(target=client_chat.receive, args=(chat,), daemon=True)
    chat_thread.start()

    while running:
        running = events(player, inv, camera, chat, sprite_groups)
        update(all_sprites, player, camera, map_rect, sprite_groups)
        draw(screen, sprite_groups["all"], map_img, map_rect, inv, chat, camera)
        clock.tick(FPS)

    sock_client.send_update('disconnect', {'id': player.id})

    pg.quit()


def main():
    run()


if __name__ == '__main__':
    main()
    quit()
