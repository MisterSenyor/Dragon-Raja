import socket
import threading
import settings
from entities import *


class chat_client:
    socket: socket

    def __init__(self, name):
        self.name = name

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print("trying to connet with server: {}".format(settings.SERVER_ADDRESS_TCP))
            self.socket.connect(settings.SERVER_ADDRESS_TCP)
            msg = self.socket.recv(settings.HEADER_SIZE).decode()
            print("the server sent: {}".format(msg))
            self.socket.send(self.name.encode())
        except Exception:
            print("exception during start method")

    def receive(self, chat):
        while True:
            try:
                message = self.socket.recv(settings.HEADER_SIZE).decode()
                print("server sent: {}".format(message))
                chat.add_line(message)
            except:
                print('Error receiving message from server, closing connection')

    def send(self, data: str):
        try:
            self.socket.send(data.encode())
        except Exception:
            print("cant send data")

    def handle(self):
        while True:
            self.receive()


def main():
    client1 = chat_client("Itamar")
    client1.start()
    receive_thread = threading.Thread(target=client1.handle)
    receive_thread.start()
    while True:
        client1.send(input("Enter data to send:"))


if __name__ == "__main__":
    main()
