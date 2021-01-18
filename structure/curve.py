from typing import Any, List

from yakuza_gmt.structure.graph import *
from yakuza_gmt.structure.types.format import CurveFormat


class Curve:
    def __init__(self):
        self.values = []

    data_path: str
    curve_format: CurveFormat
    values: List[Any]

    graph: Graph
    anm_data_offset: int
    property_fmt: int
    format: int

    def neutralize_pos(self):
        if not self.curve_format == CurveFormat.POS_VEC3:
            if 'X' in self.curve_format.name:
                self.values = [[v[0], 0.0, 0.0] for v in self.values]
            elif 'Y' in self.curve_format.name:
                self.values = [[0.0, v[0], 0.0] for v in self.values]
            elif 'Z' in self.curve_format.name:
                self.values = [[0.0, 0.0, v[0]] for v in self.values]
            self.curve_format = CurveFormat.POS_VEC3

    def neutralize_rot(self):
        if 'W' in self.curve_format.name:
            if 'X' in self.curve_format.name:
                self.values = [[v[0], 0.0, 0.0, v[1]] for v in self.values]
            elif 'Y' in self.curve_format.name:
                self.values = [[0.0, v[0], 0.0, v[1]] for v in self.values]
            elif 'Z' in self.curve_format.name:
                self.values = [[0.0, 0.0, v[0], v[1]] for v in self.values]
            self.curve_format = CurveFormat.ROT_QUAT_SCALED


def new_pos_curve():
    pos = Curve()
    pos.graph = zero_graph()
    pos.curve_format = CurveFormat.POS_VEC3
    pos.values = [(0, 0, 0)]
    return pos


def new_rot_curve():
    rot = Curve()
    rot.graph = zero_graph()
    rot.curve_format = CurveFormat.ROT_QUAT_SCALED
    rot.values = [(0, 0, 0, 1)]
    return rot
