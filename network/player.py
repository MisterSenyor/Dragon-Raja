from dataclasses import dataclass, field, asdict
from typing import Tuple

from utils import distance


@dataclass
class Player:
    """
    A class representing the server's view of a player
    """
    id: int
    name: str
    speed: float
    start_pos: Tuple[int, int]
    end_pos: Tuple[int, int] = field(default=None)
    t0: float = field(default=0)

    def __post_init__(self):
        self.end_pos = self.end_pos if self.end_pos is not None else self.start_pos

    def get_duration(self) -> float:
        """
        Calculate the duration it takes the player to complete its movement
        :return: the during in seconds as a float
        """
        return distance(self.start_pos, self.end_pos) / self.speed

    def get_pos(self, t: float) -> Tuple[int, int]:
        """
        Calculate the player's position when time=t
        :param t: time in seconds since epoch as a float
        :return: the player's position as a tuple of 2 ints
        """
        duration = self.get_duration()
        if duration == 0:
            return self.start_pos
        a = (t - self.t0) / duration
        a = min(a, 1)
        return round((1 - a) * self.start_pos[0] + a * self.end_pos[0]), round(
            (1 - a) * self.start_pos[1] + a * self.end_pos[1])

    def move(self, target: Tuple[int, int], t: float):
        """
        Start moving the player
        :param target: where to move the player to
        :param t: when the player starts its movement
        """
        self.start_pos = self.get_pos(t)
        self.end_pos = target
        self.t0 = t

    def to_dict(self) -> dict:
        """
        Convert into a dictionary
        :return: the serialized player
        """
        return asdict(self)

    def get_crossing_time(self, x: int) -> float:
        """
        Compute the time until the player x position is equal to a given int, assuming the player is moving and
        "x" is between "start" and "end"
        :param x: desired x value
        :return: seconds until player reaches x
        """
        assert self.start_pos[0] != self.end_pos[0]
        walking_part = (x - self.start_pos[0]) / (self.end_pos[0] - self.start_pos[0])
        assert 0 <= walking_part <= 1
        return self.get_duration() * walking_part
