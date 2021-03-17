from typing import List
from os.path import realpath

from .util.binary import BinaryReader


class GMDBone:
    def __init__(self):
        self.name = ""
        self.child = -1
        self.sibling = -1
        self.local_pos = ()
        self.local_rot = ()
        self.local_scale = ()
        self.global_pos = (0, 0, 0, 0)
        self.axis = ()
        self.length = 0

        self.children = []
        self.children_recursive = []
        self.parent_recursive = []
        self.parent_index = -1

    # FIXME: has duplicate bones
    def get_children_recursive(self):
        self.children_recursive = self.children
        for b in self.children:
            re_bones = [b]
            while len(re_bones):
                re_bones_new = []
                for bc in re_bones:
                    for c in bc.children:
                        # TODO: make a proper fix. this works but it's not ideal
                        if c not in self.children_recursive:
                            self.children_recursive.append(c)
                        if c.child != -1:
                            re_bones_new.append(c)
                re_bones = re_bones_new

def read_gmd_bones(path: str) -> List[GMDBone]:
    with open(realpath(path), "rb") as f:
        return read_gmd_bones_from_data(f.read())

def read_gmd_bones_from_data(data: bytearray) -> List[GMDBone]:
    gmd = BinaryReader(data)

    if gmd.read_str(4) != "GSGM":
        print("Invalid GMD magic!")
        return []

    gmd.skip(1)

    gmd.set_endian(bool(gmd.read_uint8()))

    gmd.seek(0x30)
    bone_offset = gmd.read_uint32()

    gmd.seek(0x5C)
    bone_count = gmd.read_uint32()

    gmd.seek(0x80)
    names_offset = gmd.read_uint32()

    bones = []
    for b in range(bone_count):
        bone = GMDBone()

        gmd.seek(bone_offset + (0x80 * b))

        gmd.skip(0x4)
        bone.child = gmd.read_int32()
        bone.sibling = gmd.read_int32()
        gmd.skip(0xC)
        name_index = gmd.read_int32()

        gmd.skip(4)
        bone.local_pos = gmd.read_float(4)
        bone.local_rot = gmd.read_float(4)
        bone.local_scale = gmd.read_float(4)
        bone.global_pos = gmd.read_float(4)
        bone.axis = gmd.read_float(3)
        bone.length = gmd.read_float()

        gmd.seek(names_offset + (name_index * 0x20) + 2)
        bone.name = str(gmd.read_str(30))
        bones.append(bone)

    return get_children(bones)


def get_children(bones):
    for bone in bones:
        index = bones.index(bone)
        i = bone.child
        while i != -1:
            b = bones[i]
            b.parent_index = index
            bone.children.append(b)
            i = b.sibling
    return get_parents(bones)


def get_parents(bones):
    for bone in bones:
        i = bone.parent_index
        while i != -1:
            b = bones[i]
            bone.parent_recursive.append(b)
            i = b.parent_index
    return bones


def get_face_bones(bones):
    face = [b for b in bones if 'face' in b.name][0]
    jaw = [b for b in bones if 'jaw' in b.name][0]

    i = face.child
    while i != -1:
        b = bones[i]
        face.children.append(b)
        i = b.sibling

    i = jaw.child
    while i != -1:
        b = bones[i]
        jaw.children.append(b)
        i = b.sibling

    return (face, jaw)


def find_gmd_bone(name: str, bones: List[GMDBone]):
    results = [b for b in bones if name in b.name]
    if not len(results):
        return (None, -1)
    bone = results[0]
    index = bones.index(bone)
    return (bone, index)
