import pytmx

SERVER_IP = '127.0.0.1'
SERVER_PORT = 2222

SERVER_ADDRESSES = [('127.0.0.1', p) for p in range(22220, 22224)]

SERVER_ADDRESS = (SERVER_IP, SERVER_PORT)
TCP_PORT = 59000

SERVER_ADDRESS_TCP = (SERVER_IP, TCP_PORT)

DATABASE_NAME = 'dragonraja'

USERS_FILE = r'data\Users.txt'
PLAYERS_FILE = r'data\Players.txt'

UPDATE_TICK = 0.1

HEADER_SIZE = 1024
ENCODING = 'utf-8'

TILESIZE = 64
FPS = 100

BGCOLOR = "#71ddee"

BLACK, RED = "#000000", "#FF0000"

CHUNK_SIZE = 500
LB_ADDRESS = ('127.0.0.1', 13579)
MULTIPLE_SERVERS = True
ENABLE_SHADOWS = False
MOB_COUNT = 100

MAP_COEFFICIENT = 4
tm = pytmx.TiledMap("./maps/map_new.tmx")
MAP_SIZE = (tm.width * TILESIZE * MAP_COEFFICIENT, tm.height * TILESIZE * MAP_COEFFICIENT)

CHUNKS_X, CHUNKS_Y = MAP_SIZE[0] // CHUNK_SIZE, MAP_SIZE[1] // CHUNK_SIZE
PEACEFUL_MODE = False

char_lim = 20  # chat text char lim

username_lim = 20  # username character limit

INVENTORY_SIZE = 10

PLAYER_SIZE = [50, 30]
MOB_SIZE = [50, 30]
PROJECTILE_SIZE = [40, 40]
chat_start_seed = "Barak_Gonen"

COOLDOWN_DURATIONS = {
    'projectile': 0.2,
    'skill': 5,
}

BACKUP_DELAY = 1
