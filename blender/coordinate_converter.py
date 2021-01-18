from typing import Tuple

from mathutils import Vector, Quaternion, Matrix


def transform_position_gmd_to_blender(pos: Vector) -> Vector:
    return Vector((-pos.x, pos.z, pos.y))


def transform_to_blender(pos: Vector, rot: Quaternion, scale: Vector) -> Tuple[Vector, Quaternion, Vector]:
    pos = Vector((-pos.x, pos.z, pos.y))
    rot = Quaternion((rot.w, -rot.x, rot.z, rot.y))
    scale = scale.xzy

    return pos, rot, scale


def pos_to_blender(pos):
    # return [-pos[0] / float(64), pos[2] / float(64), pos[1] / float(64)]
    return [-pos[0], pos[2], pos[1]]


def rot_to_blender(rot):
    return [rot[3], -rot[0], rot[2], rot[1]]


def pos_from_blender(pos: Vector) -> Vector:
    return Vector((-pos[0], pos[2], pos[1]))


def pos_from_blender_unscaled(pos: Vector) -> Vector:
    return Vector((-pos[0], pos[2] + 1.1, pos[1]))


def rot_from_blender(rot: Quaternion) -> Quaternion:
    return Quaternion((-rot[1], rot[3], rot[2], rot[0]))


def transform_from_blender(pos: Vector, rot: Quaternion, scale: Vector) -> Tuple[Vector, Quaternion, Vector]:
    # The transformation is symmetrical
    return transform_gmd_to_blender(pos, rot, scale)


def transform_matrix_gmd_to_blender(matrix: Matrix) -> Matrix:
    pos, rot, scale = matrix.decompose()
    pos, rot, scale = transform_gmd_to_blender(pos, rot, scale)
    return transform_to_matrix(pos, rot, scale)


def transform_matrix_blender_to_gmd(matrix: Matrix) -> Matrix:
    pos, rot, scale = matrix.decompose()
    pos, rot, scale = transform_blender_to_gmd(pos, rot, scale)
    return transform_to_matrix(pos, rot, scale)


def transform_to_matrix(pos: Vector, rot: Quaternion, scale: Vector) -> Matrix:
    scale_matrix = Matrix.Diagonal(scale)
    scale_matrix.resize_4x4()
    rot_matrix = rot.to_matrix()
    rot_matrix.resize_4x4()
    pos_matrix = Matrix.Translation(pos.xyz)
    pos_matrix.resize_4x4()
    return pos_matrix @ rot_matrix @ scale_matrix
