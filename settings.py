SERVER_IP = '127.0.0.1'
SERVER_PORT = 2222

SERVER_ADDRESSES = [('127.0.0.1', p) for p in (17494, 22225, 12763, 14763, 13853)]

SERVER_ADDRESS = (SERVER_IP, SERVER_PORT)
TCP_PORT = 59000

SERVER_ADDRESS_TCP = (SERVER_IP, TCP_PORT)

DATABASE_PORT = 2212
DATABASE_NAME = 'dragonRaja'
DATABASE_ERRORS = dict(Connection_Error='Error connecting to database', No_Such_User='Username does not exist',
                       Wrong_Password='Password does not match', Username_Exists='Username already taken',
                       Database_Error='Database malfunction', No_Such_Player='No player exists with this ID')

UPDATE_TICK = 0.1

HEADER_SIZE = 1024
ENCODING = 'utf-8'

TILESIZE = 64
FPS = 100

BGCOLOR = "#71ddee"

WIDTH, HEIGHT = 1280, 720
BLACK, RED = "#000000", "#FF0000"

CHUNK_SIZE = 500
LB_ADDRESS = ('127.0.0.1', 28300)
MULTIPLE_SERVERS = False
ENABLE_SHADOWS = False

MAP_SIZE = (10000, 5000)  # change to real value
CHUNKS_X, CHUNKS_Y = MAP_SIZE[0] // CHUNK_SIZE, MAP_SIZE[1] // CHUNK_SIZE
PEACEFUL_MODE = False

char_lim = 20  # chat text char lim

username_lim = 20  # username character limit

INVENTORY_SIZE = 15
