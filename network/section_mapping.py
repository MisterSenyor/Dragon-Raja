from dataclasses import dataclass, asdict
from typing import Tuple, Sequence

from network.utils import Address


def default_mapping(servers: Sequence[Address], map_size: Tuple[int, int]):
    """
    Create a mapping where all sections are the same size
    :param servers: servers for the mapping
    :param map_size: map size for the mapping
    :return: the new created mapping
    """
    return SectionMapping(servers=servers, map_size=map_size,
                          sections=list(range(0, map_size[0], map_size[0] // len(servers)))[:len(servers)])


@dataclass
class SectionMapping:
    """
    A class representing a mapping between map sections and server addresses
    """
    servers: Sequence[Address]
    map_size: Tuple[int, int]
    sections: Sequence[int]

    def reduce_load(self, server: Address, factor: float):
        """
        Shrink the section of a given server by a given factor and divide the area between its neighbors
        :param server: the server whose section should be shrunk
        :param factor: by how much to shrink
        """
        assert len(self.servers) > 1
        i = self.servers.index(server)
        if i == len(self.servers) - 1:
            width = self.map_size[0] - self.sections[i]
            new_width = width // factor
            self.sections[i] += width - new_width
        else:
            width = self.sections[i + 1] - self.sections[i]
            new_width = width // factor
            offset = width - new_width
            if i == 0:
                self.sections[i + 1] -= offset
            else:
                self.sections[i] += offset // 2
                self.sections[i + 1] -= offset // 2

    def get_server(self, pos: Tuple[int, int]) -> Address:
        """
        Return the server mapped to the section where the point lies
        :param pos: the point to search
        :return: the address of the server
        """
        i = 0
        while i < len(self.sections) and pos[0] >= self.sections[i]:
            i += 1
        return self.servers[i - 1]

    def to_dict(self) -> dict:
        """
        Convert to a dict
        :return: a dict representation of self
        """
        return asdict(self)
