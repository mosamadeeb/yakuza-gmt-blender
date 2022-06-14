from typing import Dict, List, Tuple

from mathutils import Matrix, Quaternion, Vector

from ..gmt_lib import *
# from ..structure.curve import Curve
from .bone_props import GMTBlenderBoneProps


def transform_position_gmd_to_blender(pos: Vector) -> Vector:
    return Vector((-pos.x, pos.z, pos.y))


def transform_to_blender(pos: Vector, rot: Quaternion, scale: Vector) -> Tuple[Vector, Quaternion, Vector]:
    pos = Vector((-pos.x, pos.z, pos.y))
    rot = Quaternion((rot.w, -rot.x, rot.z, rot.y))
    scale = scale.xzy

    return pos, rot, scale


def pos_to_blender(pos):
    return Vector([-pos[0], pos[2], pos[1]])


def rot_to_blender(rot):
    return Quaternion([rot[3], -rot[0], rot[2], rot[1]])


def pattern_to_blender(pattern: List[List[int]]) -> List[int]:
    return list(map(lambda x: x[0], pattern))


def pos_from_blender(pos: Vector) -> Vector:
    return Vector((-pos[0], pos[2], pos[1]))


def pos_from_blender_unscaled(pos: Vector) -> Vector:
    return Vector((-pos[0], pos[2] + 1.1, pos[1]))


def rot_from_blender(rot: Quaternion) -> Tuple[float]:
    return (-rot[1], rot[3], rot[2], rot[0])


def pattern_from_blender(pattern: List[int]) -> List[List[int]]:
    return [pattern, pattern[1:] + [pattern[-1]]]


def convert_gmt_curve_to_blender(curve: GMTCurve):
    curve.fill_channels()

    if curve.type == GMTCurveType.LOCATION:
        for kf in curve.keyframes:
            kf.value = pos_to_blender(kf.value)
    elif curve.type == GMTCurveType.ROTATION:
        for kf in curve.keyframes:
            kf.value = rot_to_blender(kf.value)


def transform_location(bone_props: Dict[str, GMTBlenderBoneProps], bone_name: str, values: List[Vector]):
    prop = bone_props[bone_name]
    head = prop.head
    parent_head = bone_props.get(prop.parent_name)
    if parent_head:
        parent_head = parent_head.head
    else:
        parent_head = Vector()

    loc = prop.loc
    rot = prop.rot

    values = list(map(lambda x: (
        Matrix.Translation(loc).inverted()
        @ rot.to_matrix().to_4x4().inverted()
        @ Matrix.Translation(x - head + parent_head)
        @ rot.to_matrix().to_4x4()
        @ Matrix.Translation(loc)
    ).to_translation(), values))

    return values


def transform_rotation(bone_props: Dict[str, GMTBlenderBoneProps], bone_name: str, values: List[Quaternion]):
    prop = bone_props[bone_name]

    loc = prop.loc
    rot = prop.rot
    rot_local = prop.rot_local

    values = list(map(lambda x: (
        Matrix.Translation(loc).inverted()
        @ rot.to_matrix().to_4x4().inverted()
        @ rot_local.to_matrix().to_4x4().inverted()
        @ x.to_matrix().to_4x4()
        @ rot.to_matrix().to_4x4()
        @ Matrix.Translation(loc)
    ).to_quaternion(), values))

    return values
