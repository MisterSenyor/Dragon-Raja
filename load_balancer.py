import threading

from my_server import MyJSONEncoder, default_player
from server_chat import *
from utils import *


class LoadBalancer:
    def __init__(self, sock: socket.socket, servers):
        self.socket = sock

        self.servers = servers
        self.clients = {}  # id to client address
        self.player_chunks: Dict[int, Tuple[int, int]] = {}  # id to chunk

        self.lb_fernet = Fernet(b'GdOlkJDG--qPm68eRezrMGmFgnAC5MP3auN8Ts85lkc=')
        self.fernets: Dict[bytes, Fernet] = {}  # client pk to fernet
        self.client_public_keys: Dict[Address, bytes] = {}  # client address to public key
        self.lb_private_key = load_private_ecdh_key()

        self.chunk_mapping = generate_chunk_mapping()

    def get_server(self, chunk_idx: Tuple[int, int]):
        return self.servers[self.chunk_mapping[chunk_idx[0]][chunk_idx[1]]]

    def send_cmd(self, cmd: str, params: dict, address):
        data = json.dumps({'cmd': cmd, **params}, cls=MyJSONEncoder).encode() + b'\n'
        if address not in self.servers:
            fernet = self.fernets[self.client_public_keys[address]]
        else:
            fernet = self.lb_fernet
        self.socket.sendto(fernet.encrypt(data), address)

    def connect(self, data, client, public_key):
        player = default_player(data['username'])
        chunk = get_chunk(player.start_pos)
        server = self.get_server(chunk)
        self.clients[player.id] = client
        self.player_chunks[player.id] = chunk
        self.send_cmd(cmd='connect',
                      params={'player': player, 'client': client, 'client_key': public_key.decode()},
                      address=server)
        self.send_cmd('redirect', {'server': server}, client)
        logging.debug(f'new client connected: {client=}, {player=}, {server=}, {chunk=}')

    def forward_updates(self, data, address):
        updates_by_server_idx = [[] for _ in self.servers]

        for update_idx, chunk_idx in enumerate(data['chunks']):
            update = data['updates'][update_idx]
            # redirect clients
            if update['cmd'] == 'move':
                new_server = self.get_server(get_chunk(update['pos']))
                if new_server != address:
                    client = self.clients[update['id']]
                    logging.debug(f'client changed server: {client=}, {address=}, {new_server=}')
                    self.send_cmd('redirect', {'server': new_server}, client)
                    self.send_cmd('add_client', {'client': client, 'id': update['id'],
                                                 'client_key': self.client_public_keys[client].decode()}, new_server)
                    self.send_cmd('remove_client', {'client': client, 'id': update['id']}, address)
                for adj_server_idx in range(len(self.servers)):
                    if adj_server_idx in get_adj_server_idx(self.chunk_mapping, chunk_idx) or \
                            adj_server_idx in get_adj_server_idx(self.chunk_mapping, get_chunk(update['pos'])):
                        updates_by_server_idx[adj_server_idx].append(update_idx)
            # remove client internally
            else:
                if update['cmd'] == 'disconnect':
                    update['cmd'] = 'player_leaves'
                    del self.clients[update['id']]
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
            server = self.servers[i]
            if updates_idx:
                self.send_cmd('update', {'updates': [data['updates'][update] for update in updates_idx]}, server)

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(1024)

                if address in self.servers:
                    data = json.loads(self.lb_fernet.decrypt(msg))
                    if data['cmd'] == 'forward_updates':
                        logging.debug(f'received data: {data=}, {address=}')
                        self.forward_updates(data, address)
                else:
                    public_key, data = get_pk_and_data(msg)
                    logging.debug(f'received data: {msg=}, {address=}')

                    if public_key not in self.fernets:
                        loaded_key = serialization.load_pem_public_key(public_key)
                        self.fernets[public_key] = get_fernet(loaded_key, self.lb_private_key)
                        self.client_public_keys[address] = public_key

                    data = self.fernets[public_key].decrypt(data)
                    data = json.loads(data)

                    if data["cmd"] == "connect":
                        self.connect(data=data, client=address, public_key=public_key)

            except Exception:
                logging.exception('exception while handling request')


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(LB_ADDRESS)

    lb = LoadBalancer(servers=SERVER_ADDRESSES, sock=sock)

    # setting up chat
    server_chat = ChatServer()
    threading.Thread(target=server_chat.start).start()

    # for row in lb.chunk_mapping:
    #     print(row)

    lb.receive_packets()


if __name__ == '__main__':
    main()
