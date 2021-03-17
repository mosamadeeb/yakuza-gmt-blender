from typing import List, Tuple

from mathutils import Quaternion, Vector
from ..structure.curve import Curve


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


def convert_gmt_to_blender(curve: Curve):
    if "rotation_quaternion" in curve.data_path:
        curve.neutralize_rot()
        return [rot_to_blender(v) for v in curve.values]
    elif "location" in curve.data_path:
        curve.neutralize_pos()
        return [pos_to_blender(v) for v in curve.values]
    elif "pat1" in curve.data_path:
        return pattern_to_blender(curve.values)
    return curve.values
