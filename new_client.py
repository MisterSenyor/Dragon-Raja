import logging

from client import *


class NewClient(Client):
    def __init__(self, lb_address, *args, **kwargs):
        super(NewClient, self).__init__(*args, **kwargs)
        self.lb_address = lb_address

    def send_cmd(self, cmd: str, params: dict, dst):
        self.send_data(json.dumps({'cmd': cmd, **params}).encode() + b'\n', dst)

    def get_data(self, data):
        try:
            assert data['cmd'] == 'get_data'
            # add new sprites
            ids = [o.id for o in self.sprite_groups['entity'].sprites()] + \
                  [o.item_id for o in self.sprite_groups['dropped'].sprites()]
            for player_data in data['players']:
                if player_data['id'] not in ids:
                    self.create_player(player_data)
            for mob_data in data['mobs']:
                if mob_data['id'] not in ids:
                    self.create_mob(mob_data)
            for dropped_data in data['dropped']:
                if dropped_data not in ids:
                    self.create_dropped(dropped_data)
        except Exception:
            logging.exception(f'exception in get_data')

    def connect(self, username='ariel'):
        self.send_cmd('connect', {'username': username}, self.lb_address)
        try:
            data, address = self.sock_wrapper.recv_from()
            assert data['cmd'] == 'redirect', address == self.lb_address
            logging.debug(f'received redirect from lb: {data=}')
            self.server = tuple(data['server'])

            data, address = self.sock_wrapper.recv_from()
            assert data['cmd'] == 'init', address == self.server
            self.init(data)
        except Exception:
            logging.exception(f'exception in connect')

    def receive_updates(self):
        while True:
            data, address = self.sock_wrapper.recv_from()
            try:
                cmd = data['cmd']
                if address == self.lb_address:
                    if cmd == 'redirect':
                        self.server = tuple(data['server'])
                        logging.debug(f'client redirected to: {self.server=}')
                elif address == self.server:
                    if cmd == 'update':
                        updates = data['updates']
                        non_shadow_updates = [u for u in updates if u["cmd"] != "shadows"]
                        if non_shadow_updates:
                            logging.debug(f'received updates: {non_shadow_updates}')
                        for update in updates:
                            try:
                                self.handle_update(update)
                            except Exception:
                                logging.exception('exception in update')
                    elif cmd == 'get_data':
                        logging.debug(f'received data: {data=}')
                        self.get_data(data)
                else:
                    logging.warning(f'received json from an unknown source: {data=}, {address=}')
            except Exception:
                logging.exception(f'exception while handling update: {data=}')
