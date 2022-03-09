from netWork.network_test import Network
import pygame as pg
def read_pos(str):
    str = str.split(",")
    return int(str[0]), int(str[1])

def make_pos_str(tup):
    return str(tup[0]) + "," + str(tup[1])

def main():
    clock = pg.time.Clock()
    run = True
    n = Network()
    n2 = Network()
    startPos = read_pos(make_pos_str(n.getPos()))
    print(startPos)
    print(n2.send(make_pos_str((4000, 1360))))
    a = n.send(make_pos_str((1399, 1360)))
    print(a)
    print(n.send(make_pos_str((1398, 1360))))
    print(n.send(make_pos_str((1397, 1360))))
    print(n.send(make_pos_str((1396, 1360))))
    print(n.send(make_pos_str((1395, 1360))))
    print(n2.send(make_pos_str((2001, 1360))))

    ##while run:

    ##    clock.tick(100)

    ##    playerPos = read_pos(n.send(make_pos_str((player.x, player.y))))
    ##    player.x = playerPos[0]
   ##     player.y = playerPos[1]


if __name__ == '__main__':
    main()