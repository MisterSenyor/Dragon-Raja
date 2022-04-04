import socket
import threading
from settings import *
from utils import *


def decrypt_data(data: bin, port, seed, start=False):
    """ decrypts data via port and seed, returns string"""

    # GET CORRECT SEED FOR FIRST TIME DATA ENCRYPTED:
    if start:
        seed = ascii_seed(chat_start_seed) ^ port  # BARAK GONEN XOR'd WITH PORT
    seed %= 150
    # SHIFT RIGHT BYTES:
    data = (int.from_bytes(data, byteorder='big') >> seed).to_bytes(
        len(data) - seed - seed % 3 - 1,
        byteorder='big')

    # RETURN DATA AS STRING
    data = data.decode()
    return data


class ChatServer:
    socket: socket

    def __init__(self):
        self.clients = []
        self.names = []

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(SERVER_ADDRESS_TCP)
        self.socket.listen()
        print("Chat server is up and running")
        while True:
            client, address = self.socket.accept()
            print(f'connection is established with {str(address)}')
            client.send("Connected successfully".encode())
            name = client.recv(HEADER_SIZE)

            # DECRYPT WITH START SEED
            client_port = client.getpeername()[1]
            seed = ascii_seed(chat_start_seed) ^ client_port  # BARAK GONEN XOR'd WITH PORT
            name = decrypt_data(name, client_port, seed, start=True)

            self.clients.append(client)
            self.names.append(name)
            print('The name of this client is {}'.format(name))
            client_thread = threading.Thread(target=self.handle_client, args=(client, seed,))
            client_thread.start()

    def handle_client(self, client: socket, seed):
        # GET CLIENT PORT:
        client_port = client.getpeername()[1]
        while True:
            index = self.clients.index(client)
            name = self.names[index]
            try:
                message = client.recv(HEADER_SIZE)
                if message != "":
                    # CHANGE SEED:
                    seed += (client_port + ascii_seed(chat_start_seed) % 1000)
                    data = decrypt_data(message, client_port, seed)
                    print("{} sent {}".format(name, data))
                    self.broadcast("{}: {}".format(name, data))
                else:
                    logging.error(f'Client sent empty string via chat: {name, client}')
            except Exception:
                logging.exception(f'exception while handling chat client: {name, client}')
                self.clients.remove(client)
                self.names.remove(name)
                print(f"{name} has disconnected from server")
                client.close()
                break

    def broadcast(self, message):
        for client in self.clients:
            try:
                client.send(message.encode())
            except Exception:
                print("can't send message to {}".format(client.getsockname))


def main():
    server1 = ChatServer()
    server1.start()


if __name__ == "__main__":
    main()
