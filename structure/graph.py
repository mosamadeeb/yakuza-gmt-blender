from typing import List


class Graph:
    def __init__(self):
        self.keyframes = []

    keyframes: List[int]
    value_indices: List[int]  # used for frame density changer
    delimiter: int  # not always FF


def zero_graph():
    zero = Graph()
    zero.keyframes = [0]
    zero.delimiter = -1
    return zero
