from typing import List

from .animation import *
from .bone import *
from .curve import *
from .graph import *
from .header import *
from .name import *


class GMTFile:
    def __init__(self):
        pass

    header: GMTHeader
    names: List[Name]

    animations: List[Animation]
    bones: List[Bone]
    graphs: List[Graph]
    curves: List[Curve]

    def __update_animations(self):
        for a in self.animations:
            a.bone_map_count = len(a.bones)

            a.curves = []
            for b in a.bones:
                a.curves.extend(b.curves)
            a.curve_count = len(a.curves)

            a.graphs = []
            for c in a.curves:
                if c.graph.keyframes not in [g.keyframes for g in a.graphs]:
                    a.graphs.append(c.graph)
            a.graph_count = len(a.graphs)

            # Turned out to be last frame, not frame count
            frame_count = 0
            for g in a.graphs:
                frame_count = max(frame_count, g.keyframes[-1])
            a.frame_count = frame_count

    def __update_bones(self):
        self.bones = []
        for a in self.animations:
            self.bones.extend(a.bones)

    def __update_curves(self):
        self.curves = []
        for b in self.bones:
            self.curves.extend(b.curves)

    def __update_graphs(self):
        self.graphs = []
        for c in self.curves:
            if c.graph.keyframes not in [g.keyframes for g in self.graphs]:
                self.graphs.append(c.graph)

    def __update_names(self):
        self.names = [a.name for a in self.animations]
        for a in self.animations:
            self.names.extend([b.name for b in a.bones])

    def __update_header(self):
        self.header.anm_count = len(self.animations)
        self.header.bone_map_count = len(self.bones)
        self.header.name_count = len(self.names)
        self.header.curve_count = len(self.curves)
        self.header.graph_count = len(self.graphs)

    def update(self):
        self.__update_animations()
        self.__update_bones()
        self.__update_curves()
        self.__update_graphs()
        self.__update_names()
        self.__update_header()
