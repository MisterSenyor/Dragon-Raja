from client import *


class NewClient(Client):
    def __init__(self, lb_address, *args, **kwargs):
        super(NewClient, self).__init__(*args, **kwargs)
        self.lb_address = lb_address

    def send_cmd(self, cmd: str, params: dict, dst):
        self.sock.sendto(json.dumps({'cmd': cmd, **params}).encode() + b'\n', dst)

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
                        if updates:
                            logging.debug(f'received updates: {updates=}')
                        for update in updates:
                            self.handle_update(update)
                else:
                    logging.warning(f'received json from an unknown source: {data=}, {address=}')
            except Exception:
                logging.exception(f'exception while handling update: {data=}')
