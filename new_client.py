from client import *


class NewClient(Client):
    def __init__(self, lb_address, *args, **kwargs):
        super(NewClient, self).__init__(*args, **kwargs)
        self.lb_address = lb_address

    def send_cmd(self, cmd: str, params: dict, dst):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode() + b'\n', dst)

    def init(self, username='ariel'):
        self.send_cmd('connect', {'username': username}, self.lb_address)
        try:
            data = recv_json(self.sock, self.lb_address)
            assert data['cmd'] == 'redirect'
            logging.debug(f'received redirect from lb: {data=}')
            self.server = tuple(data['server'])

            data = recv_json(self.sock, self.server)
            assert data['cmd'] == 'init'
            self.main_player = self.create_main_player(data['main_player'])
            for player_data in data['players']:
                self.create_player(player_data)
            for mob_data in data['mobs']:
                self.create_mob(mob_data)
            for projectile_data in data['projectiles']:
                self.create_projectile(projectile_data)
            for dropped_data in data['dropped']:
                self.create_dropped(dropped_data)
        except Exception:
            logging.exception(f'exception in init')

    def receive_updates(self):
        while True:
            data, address = recv_json(self.sock, None)
            try:
                cmd = data['cmd']
                if address == self.lb_address:
                    if cmd == 'redirect':
                        self.server = tuple(data['server'])
                        logging.debug(f'client redirected to: {self.server=}')
                elif address == self.server:
                    if cmd == 'update':
                        updates = data['updates']
                        if updates:
                            logging.debug(f'received updates: {updates=}')
                        for update in updates:
                            self.handle_update(update)
                else:
                    logging.warning(f'received json from an unknown source: {data=}, {address=}')
            except Exception:
                logging.exception(f'exception while handling update: {data=}')
