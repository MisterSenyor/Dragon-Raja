from my_server import *
from settings import *


class NewServer(Server):
    def __init__(self, sock: socket.socket, lb_address, chunks: List[Tuple[int, int]]):
        super(NewServer, self).__init__(sock=sock)
        self.lb_address = lb_address
        self.chunks = chunks

    def connect(self, data, address):
        player = Player(id=None, start_pos=(1400, 1360), end_pos=None,
                        health=100, items=[], t0=0, username=data['username'])
        self.updates.append({'cmd': 'player_enters', 'player': player})

        data = json.dumps({
            'cmd': 'init',
            'main_player': player,
            'players': list(self.players.values()),
            'mobs': list(self.mobs.values()),
            'projectiles': self.projectiles
        }, cls=MyJSONEncoder).encode() + b'\n'
        send_all(self.socket, data, address)

        self.clients.append(address)
        self.players[player.id] = player

        logging.debug(f'new client connected: {address=}, {player=}')

    def disconnect(self, data, address):
        self.clients.remove(address)

        del self.players[data['id']]
        self.updates.append({'cmd': 'player_leaves', 'id': data['id']})

        logging.debug(f'client disconnected: {address=}, {data=}')

    def handle_update(self, data, address, forward=True):
        cmd = data['cmd']
        player = self.players[data['id']]
        t = time.time_ns()
        if cmd == 'move':
            player.move(data['pos'])
        elif cmd == 'projectile':
            proj = Projectile(**data['projectile'], start_pos=player.get_pos(t), t0=t, id=None)
            self.projectiles[proj.id] = proj
        elif cmd == 'attack':
            self.attacking_players.append(player.id)
        self.updates.append(data)

    def add_client(self, data, address):
        pass

    def remove_client(self, data, address):
        pass

    def receive_packets(self):
        while True:
            try:
                msg, address = self.socket.recvfrom(settings.HEADER_SIZE)
                data = json.loads(msg.decode())
                logging.debug(f'received data: {data=}, {address=}')

                cmd = data['cmd']
                if address == self.lb_address:
                    if cmd == "connect":
                        self.connect(data=data, address=address)
                    elif cmd == 'add_client':
                        self.add_client(data=data, address=address)
                    elif cmd == 'remove_client':
                        self.remove_client(data=data, address=address)
                    elif cmd == 'update':
                        self.handle_update(data=data, address=address, forward=False)
                elif data["cmd"] == "disconnect":
                    self.disconnect(data=data, address=address)
                else:
                    self.handle_update(data=data, address=address)
            except Exception:
                logging.exception('exception while handling request')

    def send_updates(self):
        data = json.dumps({'cmd': 'update', 'updates': self.updates}, cls=MyJSONEncoder).encode() + b'\n'
        self.updates.clear()
        for client in self.clients:
            send_all(self.socket, data, client)


def main():
    logging.basicConfig(level=logging.DEBUG)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(settings.SERVER_ADDRESS)

    chunks = []
    server = NewServer(sock=sock, lb_address=LB_ADDRESS, chunks=chunks)
    receive_thread = threading.Thread(target=server.receive_packets)
    receive_thread.start()

    while True:
        time.sleep(settings.UPDATE_TICK)
        server.update_mobs()
        server.collisions_handler()
        server.send_updates()


if __name__ == '__main__':
    main()
