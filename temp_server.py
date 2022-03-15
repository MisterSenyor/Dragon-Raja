import logging
import queue
import socket
import threading
from settings import *
import json
import time


class UDPServer:
    def __init__(self):
        self.IP = SERVER_IP  # Host address
        self.port = SERVER_PORT  # Host port
        self.sock = None  # Socket
        self.HEADER_SIZE = HEADER_SIZE
        self.ENCODING = ENCODING
        self.currentPlayer = 0
        self.Addresses = []
        self.updates_queue = queue.Queue()

    def start_server(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            self.sock.bind((self.IP, self.port))
        except socket.error as e:
            str(e)
        print("server started")

    def threaded_client(self):
        while True:
            (data, addr) = self.sock.recvfrom(self.HEADER_SIZE)
            cmd, params = self.parse_cmd(data)
            if cmd == "connect":
                self.new_client(addr)

            ##player = self.curr_client(params["id"])

            print("Received: ", cmd)
            self.updates_queue.put({"update": cmd, **params})

    def threaded_queue_send(self):
        while True:
            time.sleep(0.05)
            self.threaded_send()

    def threaded_send(self):
        update = ""
        while self.updates_queue is None:
            update += self.updates_queue.get()

        if update != "":
            for addres in self.Addresses:
                self.sock.sendto(update.encode(), addres)

    def wait_for_client(self):
        thread_recv = threading.Thread(target=self.threaded_client)
        thread_queue = threading.Thread(target=self.threaded_queue_send)
        thread_recv.start()
        thread_queue.start()

    def parse_cmd(self, data):
        """
        Parse cmd and params from a given message
        :param data: the message to parse
        :return: a tuple (cmd, params) parsed from the data
        """

        try:
            data = data.decode()
            cmd = json.loads(data)["cmd"]
            json_data = "{" + data.split(",", 1)[1]
            return cmd, json.loads(json_data)
        except Exception:
            logging.exception(f'exception while parsing cmd: {data}')
            return '', {}

    def new_client(self, addr):
        data = json.dumps({'cmd': 'connect', 'id': self.currentPlayer})
        self.sock.sendto(data.encode(), addr)
        self.currentPlayer += 1
        self.Addresses.append(addr)

    def curr_client(self, id):
        player = 1
        for x in range(1, self.currentPlayer):
            if x == id:
                return player
            player += 1


def main():
    server = UDPServer()
    server.start_server()
    server.wait_for_client()


if __name__ == '__main__':
    main()
