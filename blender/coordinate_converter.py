from typing import Dict, List, Tuple

from mathutils import Matrix, Quaternion, Vector

from ..gmt_lib import *
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


def pattern1_to_blender(pattern: List[List[int]]) -> List[int]:
    return list(map(lambda x: (x[0],), pattern))


def pattern2_to_blender(pattern: List[int]) -> List[int]:
    # No need to change anything for now
    return pattern


def pos_from_blender(pos: Vector) -> Tuple[float]:
    return (-pos[0], pos[2], pos[1])


def rot_from_blender(rot: Quaternion) -> Tuple[float]:
    return (-rot[1], rot[3], rot[2], rot[0])


def pattern1_from_blender(pattern: List[int]) -> List[List[int]]:
    return [pattern, pattern[1:] + [pattern[-1]]]


def pattern2_from_blender(pattern: List[int]) -> List[List[int]]:
    return pattern


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

    pre_mat = (
        Matrix.Translation(loc).inverted()
        @ rot.to_matrix().to_4x4().inverted()
    )

    post_mat = (
        rot.to_matrix().to_4x4()
        @ Matrix.Translation(loc)
    )

    values = list(map(lambda x: (pre_mat @ Matrix.Translation(x - head + parent_head) @ post_mat).to_translation(), values))

    return values


def transform_rotation(bone_props: Dict[str, GMTBlenderBoneProps], bone_name: str, values: List[Quaternion]):
    prop = bone_props[bone_name]

    parent_rot = bone_props.get(prop.parent_name)
    if parent_rot:
        parent_rot = parent_rot.rot_local
    else:
        parent_rot = Quaternion()

    loc = prop.loc
    rot = prop.rot
    rot_local = prop.rot_local

    # HACK: Treat DE and OE animations differntly when it comes to local rotation
    # This is just to make sure the finger bones look the best they can with both skeleton types
    if bone_props.get('sync_c_n'):
        # DE
        pre_mat = (Matrix.Identity(4)
            @ rot.to_matrix().to_4x4().inverted()
            @ parent_rot.to_matrix().to_4x4()
        )

        post_mat = (Matrix.Identity(4)
            @ rot_local.to_matrix().to_4x4().inverted()
            @ parent_rot.to_matrix().to_4x4().inverted()
            @ rot.to_matrix().to_4x4()
        )
        
        # pre_mat = rot.inverted() @ parent_rot
        # post_mat = rot_local.inverted() @ parent_rot.inverted() @ rot
        
        # kinda better hack
        # pre_mat = (Matrix.Identity(4)
            
        #     @ rot.to_matrix().to_4x4().inverted()
        #     @ rot_local.to_matrix().to_4x4().inverted()
        #     #@ parent_rot.to_matrix().to_4x4()#.inverted()
        #     #@ Matrix.Translation(loc).inverted()
        # )

        # post_mat = (Matrix.Identity(4)
        #     #@ Matrix.Translation(loc)
        #     #@ rot_local.to_matrix().to_4x4().inverted()
        #     @ parent_rot.to_matrix().to_4x4().inverted()
            
        #     @ rot.to_matrix().to_4x4()
        # )
        
        # better working hack
        # pre_mat = (Matrix.Identity(4)
        #     #@ rot_local.to_matrix().to_4x4().inverted()
        #     @ rot.to_matrix().to_4x4().inverted()
        #     #@ parent_rot.to_matrix().to_4x4()#.inverted()
        #     #@ Matrix.Translation(loc).inverted()
        # )

        # post_mat = (Matrix.Identity(4)
        #     #@ Matrix.Translation(loc)
        #     @ rot_local.to_matrix().to_4x4().inverted()
        #     @ parent_rot.to_matrix().to_4x4().inverted()
        #     @ rot.to_matrix().to_4x4()
        # )
        
        # semi working hack
        # pre_mat = (Matrix.Identity(4)
        #     #@ rot_local.to_matrix().to_4x4().inverted()
        #     @ rot.to_matrix().to_4x4().inverted()
        #     #@ parent_rot.to_matrix().to_4x4()#.inverted()
        #     #@ Matrix.Translation(loc).inverted()
        # )

        # post_mat = (Matrix.Identity(4)
        #     #@ Matrix.Translation(loc)
        #     @ rot_local.to_matrix().to_4x4().inverted()
        #     @ parent_rot.to_matrix().to_4x4()
        #     @ rot.to_matrix().to_4x4()
        # )
    else:
        # OE
        pre_mat = (
            Matrix.Translation(loc).inverted()
            # @ parent_rot.to_matrix().to_4x4().inverted()
            @ rot.to_matrix().to_4x4().inverted()
            @ parent_rot.to_matrix().to_4x4()
            # @ rot_local.to_matrix().to_4x4().inverted()
        )

        post_mat = (
            rot_local.to_matrix().to_4x4().inverted()
            @ parent_rot.to_matrix().to_4x4().inverted()
            @ rot.to_matrix().to_4x4()
            @ Matrix.Translation(loc)
        )
        
        # pre_mat = (
        #     Matrix.Translation(loc).inverted()
        #     # @ parent_rot.to_matrix().to_4x4().inverted()
        #     @ rot.to_matrix().to_4x4().inverted()
        #     # @ rot_local.to_matrix().to_4x4().inverted()
        # )

        # post_mat = (
        #     rot_local.to_matrix().to_4x4().inverted()
        #     @ rot.to_matrix().to_4x4()
        #     @ parent_rot.to_matrix().to_4x4()
        #     @ Matrix.Translation(loc)
        # )

    values = list(map(lambda x: (pre_mat @ x.to_matrix().to_4x4() @ post_mat).to_quaternion(), values))
    
    # values = list(map(lambda x: pre_mat @ x @ post_mat, values))

    return values


# pre_mat = (Matrix.Identity(4)
#     @ Matrix.Translation(loc).inverted()
#     #@ rot_local.to_matrix().to_4x4().inverted()
#     @ rot.to_matrix().to_4x4().inverted()
# )

# post_mat = (
#     Matrix.Identity(4)
#     #@ parent_rot.to_matrix().to_4x4()
#     @ rot.to_matrix().to_4x4()
#     @ rot_local.to_matrix().to_4x4().inverted()
#     @ Matrix.Translation(loc)
# )
