from typing import List

from yakuza_gmt.structure.curve import Curve
from yakuza_gmt.structure.graph import Graph
from yakuza_gmt.structure.name import Name
from yakuza_gmt.structure.types.format import CurveFormat


class Bone:
    def __init__(self):
        self.curves = []

    name: Name

    curves: List[Curve]

    def position_curves(self):
        return [c for c in self.curves if 'POS' in c.curve_format.name]

    def rotation_curves(self):
        return [c for c in self.curves if 'ROT' in c.curve_format.name]


def find_bone(name: str, bones: List[Bone]):
    results = [b for b in bones if name in b.name.string()]
    if not len(results):
        return (None, -1)
    bone = results[0]
    index = bones.index(bone)
    return (bone, index)
