import logging
from typing import Optional
from client import *


class NewClient(Client):
    def __init__(self, lb_address, *args, **kwargs):
        super(NewClient, self).__init__(*args, **kwargs)
        self.lb_address = lb_address

    def send_cmd(self, cmd: str, params: dict, dst):
        self.send_data(json.dumps({'cmd': cmd, **params}).encode(), dst)

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

    def connect(self, username, password, action) -> Optional[str]:
        """
        connect to the load balancer using the given username and password
        :param username: the username
        :param password: the password
        :param action: either 'login' or 'sign_up'
        :return: the error message on error and None on success
        """
        self.send_cmd('connect', {'username': username, 'password': password, 'action': action}, self.lb_address)
        try:
            data, address = self.sock_wrapper.recv_from()
            if data['cmd'] == 'error':
                return data['message']

            assert data['cmd'] == 'redirect', address == self.lb_address
            logging.debug(f'received redirect from lb: {data=}')
            self.server = tuple(data['server'])

            data, address = self.sock_wrapper.recv_from()
            assert data['cmd'] == 'init', address == self.server
            self.init(data)
        except Exception:
            logging.exception(f'exception in connect')

    def remove_data(self, data):
        for entity_id in data['entities']:
            entity = self.get_entity_by_id(entity_id)
            entity.kill()

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
                elif cmd == 'remove_data':
                    logging.debug(f'removing data: {data=}')
                    self.remove_data(data)
                else:
                    logging.warning(f'received json from an unknown source: {data=}, {address=}')
            except Exception:
                logging.exception(f'exception while handling update: {data=}')
