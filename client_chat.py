import socket
import threading
import settings
from settings import *
from entities import *
from utils import *


class ChatClient:
    socket: socket

    def __init__(self, name):
        self.name = name
        self.seed = chat_start_seed
        self.port = None

    def start(self):
        # SET UP SOCKET
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # CONNECT TO SERVER:
            print("trying to connet with server: {}".format(SERVER_ADDRESS_TCP))
            self.socket.connect(SERVER_ADDRESS_TCP)

            # GET PORT NUMBER:
            self.port = (self.socket.getsockname()[1])

            # RECEIVE MSG
            msg = self.socket.recv(HEADER_SIZE).decode()
            print("the server sent: {}".format(msg))

            # ENCRYPT AND SEND NAME
            encrypted_name = self.encrypt_data(self.name, True)
            self.socket.send(encrypted_name)
        except Exception:
            logging.exception(f'Error while starting chat, closing connection')

    def receive(self, chat):
        while True:
            try:
                message = self.socket.recv(HEADER_SIZE).decode()
                if message != '':
                    print("server sent: {}".format(message))
                    chat.add_line(message)
            except Exception:
                logging.exception(f'Error receiving message from server, closing connection')

    def send(self, data: str):
        try:
            # UPDATE SEED:
            self.seed += (self.port + ascii_seed(chat_start_seed)) % 1000
            encrypted = self.encrypt_data(data)
            self.socket.send(encrypted)
        except Exception:
            logging.exception(f'exception while sending data: {data}')

    def encrypt_data(self, data: str, start=False):
        """ encrypts and encodes data as bytes """

        encrypted_data = data.encode()
        if start:
            self.seed = ascii_seed(self.seed) ^ self.port  # BARAK GONEN XOR'd WITH PORT
        self.seed %= 150
        # SHIFT LEFT BYTES:
        encrypted_data = (int.from_bytes(encrypted_data, byteorder='big') << self.seed).to_bytes(
            len(encrypted_data) + self.seed + self.seed % 3 + 1,
            byteorder='big')
        # RETURN ENCRYPTED DATA AS BYTES
        return encrypted_data

    def handle(self):
        while True:
            self.receive()


def main():
    client1 = ChatClient("Itamar")
    client1.start()
    receive_thread = threading.Thread(target=client1.handle)
    receive_thread.start()
    while True:
        client1.send(input("Enter data to send:"))


if __name__ == "__main__":
    main()
