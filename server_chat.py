import socket
import threading
import settings


class chat_server:
    socket: socket

    def __init__(self):
        self.clients = []
        self.names = []

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(settings.SERVER_ADDRESS_TCP)
        self.socket.listen()
        print("Chat server is up and running")
        while True:
            client, address = self.socket.accept()
            print(f'connection is established with {str(address)}')
            client.send("Connected successfully".encode())
            name = client.recv(settings.HEADER_SIZE).decode()
            self.clients.append(client)
            self.names.append(name)
            print('The name of this client is {}'.format(name))
            client_thread = threading.Thread(target=self.handle_client, args=(client,))
            client_thread.start()

    def handle_client(self, client: socket):
        while True:
            index = self.clients.index(client)
            name = self.names[index]
            try:
                message = client.recv(settings.HEADER_SIZE).decode()
                print("{} sent {}".format(name, message))
                if (message != ""):
                    self.broadcast("{}: {}".format(name, message))
                else:
                    raise Exception
            except Exception:
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
    server1 = chat_server()
    server1.start()


if __name__ == "__main__":
    main()
