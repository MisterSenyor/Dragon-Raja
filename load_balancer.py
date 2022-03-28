from typing import Tuple, Collection

from settings import *


class LoadBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.chunks_x = WIDTH // CHUNK_SIZE
        self.chunks_y = HEIGHT // CHUNK_SIZE
        self.chunks = [[[] for _ in range(self.chunks_y)] for _ in range(self.chunks_x)]
        self.generate_chunks()

    def generate_chunks(self):
        for i in range(self.chunks_x):
            for j in range(self.chunks_y):
                mid_x = self.chunks_x // 2
                mid_y = self.chunks_y // 2
                if i <= mid_x:
                    if j <= mid_y:
                        self.chunks[i][j].append(self.servers[0])
                    if j >= mid_y:
                        self.chunks[i][j].append(self.servers[1])
                if i >= mid_x:
                    if j <= mid_y:
                        self.chunks[i][j].append(self.servers[2])
                    if j >= mid_y:
                        self.chunks[i][j].append(self.servers[3])

    def get_servers(self, pos: Tuple[int, int]) -> Collection:
        return self.chunks[pos[0] // CHUNK_SIZE][pos[1] // CHUNK_SIZE]


def main():
    lb = LoadBalancer([('127.0.0.1', p) for p in [10000, 20000, 30000, 40000]])
    print(lb.chunks_x, lb.chunks_y, lb.chunks)
    print(lb.get_servers((50, 300)))


if __name__ == '__main__':
    main()
