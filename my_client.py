import socket
import settings
import json


def main():
    my_scoket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msg = {'cmd': 'new'}
    print("sending: {}".format(msg))
    data = json.dumps(msg).encode()
    my_scoket.sendto(data, settings.SERVER_ADDRESS)
    data, address = my_scoket.recvfrom(settings.HEADER_SIZE)
    data = json.loads(data.decode())
    id = data["id"]
    print("received: {}".format(data))
    msg = {'cmd': 'disconnect'}
    print("sending: {}".format(msg))
    data = json.dumps(msg).encode()
    my_scoket.sendto(data, settings.SERVER_ADDRESS)
    data, address = my_scoket.recvfrom(settings.HEADER_SIZE)
    data = json.loads(data.decode())
    print("received: {}".format(data))


if __name__ == '__main__':
    main()
