import socket
import threading


class UDPServer:
    def __init__(self):
        self.IP = socket.gethostbyname(socket.gethostname())  # Host address
        self.port = 1337  # Host port
        self.sock = None  # Socket
        self.HEADER_SIZE = 32
        self.ENCODING = 'utf-8'
        self.Addresses = [(self.IP, self.port)]
        self.pos = [(1400, 1360)]
        self.currentPlayer = 0

    def start_server(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            self.sock.bind((self.IP, self.port))
        except socket.error as e:
            str(e)
        print("server started")

    def read_pos(self, str):
        str = str.split(",")
        return int(str[0]), int(str[1])

    def make_pos_str(self, tup):
        return str(tup[0]) + "," + str(tup[1])

    def threaded_client(self, data, addr):
        player = self.curr_client(addr)
        self.sock.sendto(str.encode(self.make_pos_str(self.pos[player])), addr)
        reply = ""
        self.pos[player] = data
        player = 0
        for addres in self.Addresses:
            if addres[0] != addr[0]:
                reply += self.make_pos_str(self.pos[player])
            player += 1
        print("Received", data)
        if reply != "":
            print("sending: ", reply)
            self.sock.sendto(str.encode(self.make_pos_str(reply)), addr)
        print("lost connection")

    def wait_for_client(self):
        while True:
            (data, addr) = self.sock.recvfrom(self.HEADER_SIZE)
            data = self.read_pos(data.decode())
            self.new_client(addr, data)
            if not data:
                print("disconnected")
            else:

                client_thread = threading.Thread(target=self.threaded_client, args=(data, addr))
                client_thread.deamon = True
                client_thread.start()

    def new_client(self, addr, data):
        for addres in self.Addresses:
            if addres[0] == addr[0]:
                return
        print(addr, "    ", self.Addresses[0][0])
        self.currentPlayer += 1
        self.Addresses.append(addr)
        self.pos.append(data)

    def curr_client(self, addr):
        player = 0
        for addres in self.Addresses:
            if addres[0] == addr[0]:
                return player
            player += 1





def main():

    server = UDPServer()
    server.start_server()
    server.wait_for_client()


if __name__ == '__main__':
    main()
