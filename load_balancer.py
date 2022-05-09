import os
import threading

from my_server import json_encode, default_player
from server_chat import *
from utils import *
from database import DBAPI
import string


def check_strong_password(password: str):
    for grp in [string.ascii_lowercase, string.ascii_uppercase, string.digits]:
        if all(let not in password for let in grp):
            return False
    if len(password) < 8 or len(password) > 25:
        return False
    return True


def check_valid_username(username: str):
    separators = '._ '
    if len(username) > 20:
        return False
    if any(let not in string.ascii_letters + string.digits + separators for let in username):
        return False
    if all(let in separators for let in username):
        return False
    return True


class LoadBalancer:
    def __init__(self, sock: socket.socket, servers, db_username, db_password, db_port):
        self.socket = sock

        self.servers = servers
        self.id_to_chunk: Dict[int, Tuple[int, int]] = {}  # id to chunk

        self.id_to_pk = {}
        self.id_to_fernet = {}
        self.id_to_address = {}

        self.lb_private_key = load_private_ecdh_key()

        self.chunk_mapping = generate_chunk_mapping()
        with open("super_secret_do_not_touch.txt", 'rb') as secret_key:
            self.lb_fernet = Fernet(secret_key.read())

        self.dbapi = DBAPI(user=db_username, password=db_password, port=db_port)

    def get_server(self, chunk_idx: Tuple[int, int]):
        return self.servers[self.chunk_mapping[chunk_idx[0]][chunk_idx[1]]]

    def send_cmd(self, cmd: str, params: dict, address, player_id=None, fernet=None, **kwargs):
        data = json_encode({'cmd': cmd, **params}, **kwargs)
        if fernet is None:
            if player_id is not None:
                fernet = self.id_to_fernet[player_id]
            else:
                fernet = self.lb_fernet
        self.socket.sendto(fernet.encrypt(data), address)

    def connect(self, data, address, public_key, fernet):
        message = None
        if data['action'] == 'login':
            if not self.dbapi.verify_account(username=data['username'], password=data['password']):
                message = 'wrong username or password'
        elif data['action'] == 'sign_up':
            if self.dbapi.check_account_exists(username=data['username']):
                message = 'account already exists'
            elif not check_strong_password(password=data['password']):
                message = 'password too weak'
            elif not check_valid_username(username=data['username']):
                message = 'invalid username'
            else:
                self.dbapi.add_account(username=data['username'], password=data['password'])
                player = default_player(username=data['username'])
                self.dbapi.store_player(player)

        player = None
        if message is None:
            player = self.dbapi.retrieve_player(data['username'])
            if player.id in self.id_to_address:
                message = 'client already connected'

        if message is not None:
            logging.info(f'client connection failed: {data=}, {message=}')
            self.send_cmd('error', {'message': message}, address, fernet=fernet)
            return

        chunk = get_chunk(player.start_pos)
        server_address = self.get_server(chunk)

        self.id_to_chunk[player.id] = chunk
        self.id_to_address[player.id] = address
        self.id_to_fernet[player.id] = fernet
        self.id_to_pk[player.id] = public_key

        self.send_cmd(cmd='connect',
                      params={'player': player, 'client': address, 'client_key': public_key.decode()},
                      address=server_address, items=True)

        self.send_cmd('redirect', {'server': server_address}, address, fernet=fernet)
        logging.debug(f'new client connected: {address=}, {player=}, {server_address=}, {chunk=}')

    def player_leaves(self, player):
        logging.debug(f'client died or disconnected: {player=}')
        self.dbapi.delete_player(username=player['username'])
        self.dbapi.store_player(player)

        del self.id_to_address[player['id']]
        del self.id_to_pk[player['id']]
        del self.id_to_fernet[player['id']]
        del self.id_to_chunk[player['id']]

    def forward_updates(self, data, server_address):
        updates_by_server_idx = [[] for _ in self.servers]

        for update_idx, chunk_idx in enumerate(data['chunks']):
            update = data['updates'][update_idx]
            # redirect clients
            if update['cmd'] == 'move':
                new_server = self.get_server(get_chunk(update['pos']))
                if new_server != server_address:
                    player_id = update['id']
                    client_address = self.id_to_address[player_id]
                    logging.debug(f'client changed server: {client_address=}, {server_address=}, {new_server=}')
                    self.send_cmd('redirect', {'server': new_server}, client_address, player_id=player_id)
                    self.send_cmd('add_client', {'client': client_address, 'id': player_id,
                                                 'client_key': self.id_to_pk[player_id].decode()}, new_server)
                    self.send_cmd('remove_client', {'client': client_address, 'id': player_id}, server_address)
                for adj_server_idx in range(len(self.servers)):
                    if adj_server_idx in get_adj_server_idx(self.chunk_mapping, chunk_idx) or \
                            adj_server_idx in get_adj_server_idx(self.chunk_mapping, get_chunk(update['pos'])):
                        updates_by_server_idx[adj_server_idx].append(update_idx)
            # remove client internally
            else:
                if update['cmd'] == 'disconnect':
                    update['cmd'] = 'player_leaves'
                    player = update.pop('player')
                    self.player_leaves(player)
                if update['cmd'] == 'entity_died' and update['id'] in self.id_to_address:  # if player died
                    player = update.pop('player')
                    self.player_leaves(player)

                for adj_server_idx in get_adj_server_idx(chunk_mapping=self.chunk_mapping, chunk_idx=chunk_idx):
                    updates_by_server_idx[adj_server_idx].append(update_idx)

        for move_data in data['moving_players']:
            start_chunk, end_chunk, player = move_data['start_chunk'], move_data['end_chunk'], move_data['player']
            adj_start = get_adj_server_idx(self.chunk_mapping, start_chunk)
            adj_end = get_adj_server_idx(self.chunk_mapping, end_chunk)
            data['updates'].append({
                'cmd': 'player_enters', 'player': player
            })
            data['updates'].append({
                'cmd': 'player_leaves', 'id': player['id']
            })
            for server_idx in adj_end:
                if server_idx not in adj_start:
                    # player enters server
                    updates_by_server_idx[server_idx].insert(0, len(data['updates']) - 2)
            for server_idx in adj_start:
                if server_idx not in adj_end:
                    # player leaves server
                    updates_by_server_idx[server_idx].append(len(data['updates']) - 1)

        logging.debug(f'sent updates: {updates_by_server_idx=}')
        for i, updates_idx in enumerate(updates_by_server_idx):
            server_address = self.servers[i]
            if updates_idx:
                self.send_cmd('update', {'updates': [data['updates'][update] for update in updates_idx]}, server_address)

    def backup(self, data, address):
        logging.debug(f'backing up data: {address=}, {data=}')
        self.dbapi.update_players(data['players'].values())

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(1024)

                if address in self.servers:
                    data = json.loads(self.lb_fernet.decrypt(msg))
                    logging.debug(f'received data from server: {data=}, {address=}')
                    if data['cmd'] == 'forward_updates':
                        self.forward_updates(data, address)
                    if data['cmd'] == 'backups':
                        self.backup(data, address)
                else:
                    if msg.startswith(b'-----BEGIN PUBLIC KEY-----'):

                        public_key, data = get_pk_and_data(msg)

                        loaded_key = serialization.load_pem_public_key(public_key)
                        fernet = get_fernet(loaded_key, self.lb_private_key)

                        data = fernet.decrypt(data)
                        data = json.loads(data)
                        logging.debug(f'received data from client: {address=}, {data=}')

                        if data["cmd"] == "connect":
                            self.connect(data=data, address=address, public_key=public_key, fernet=fernet)

            except Exception:
                logging.exception('exception while handling request')


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(LB_ADDRESS)

    lb = LoadBalancer(servers=SERVER_ADDRESSES, sock=sock, db_username=os.environ['MYSQL_USER'],
                      db_password=os.environ['MYSQL_PASSWORD'], db_port=os.environ['MYSQL_PORT'])

    # setting up chat
    server_chat = ChatServer()
    threading.Thread(target=server_chat.start).start()

    lb.receive_packets()


if __name__ == '__main__':
    main()
