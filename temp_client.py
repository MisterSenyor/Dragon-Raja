from temp_network import Network
import pygame as pg

def main():
    n2 = Network()
    n = Network()
    print(n2.id)
    print(n.id)
    n.send(n.serialize_cmd({"cmd": "attack", "id": n.id}))
    ##while run:

    ##    clock.tick(100)

    ##    playerPos = read_pos(n.send(make_pos_str((player.x, player.y))))
    ##    player.x = playerPos[0]
   ##     player.y = playerPos[1]


if __name__ == '__main__':
    main()