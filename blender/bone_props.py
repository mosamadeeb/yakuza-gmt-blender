from typing import Dict, Tuple

import bpy
from mathutils import Quaternion, Vector

from .coordinate_converter import pos_to_blender, rot_to_blender


class GMTBoneProps:
    head: Vector
    loc: Vector
    rot: Quaternion
    rot_local: Quaternion
    parent_name: str


def get_edit_bones_props() -> Dict[str, GMTBoneProps]:
    ao = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')

    bone_props = {}
    for b in ao.data.edit_bones:
        bp = GMTBoneProps()
        bp.parent_name = b.parent.name if b.parent else ""

        if "head_no_rot" in b:
            bp.head = Vector(b["head_no_rot"].to_list())
        else:
            bp.head = b.head
        
        if "local_rot" in b:
            bp.rot_local = Quaternion(b["local_rot"].to_list())
        else:
            bp.rot_local = Quaternion()

        bp.loc = b.matrix.to_translation()
        bp.rot = b.matrix.to_quaternion()

        bone_props[b.name] = bp
    bpy.ops.object.mode_set(mode='POSE')
    return bone_props


def get_gmd_bones_props(gmd_bones) -> Dict[str, Tuple[Vector, str]]:
    heads = {}
    for b in gmd_bones:
        parent_name = b.parent_recursive[0].name if len(
            b.parent_recursive) else ""
        heads[b.name] = (pos_to_blender(Vector(b.global_pos[:3])), parent_name)

    if not len(heads):
        return get_edit_bones_props()

    return heads

# FIXME: This needs to be updated according to the recent changes in the importer

# def get_gmd_bones_props(gmd_bones) -> Dict[str, GMTBoneProps]:
#     bone_props = {}
#     for b in gmd_bones:
#         bp = GMTBoneProps()
#         bp.parent_name = b.parent_recursive[0].name if len(
#             b.parent_recursive) else ""

#         bp.head = pos_to_blender(Vector(b.global_pos[:3]))
#         bp.loc = pos_to_blender(Vector(b.global_pos[:3]))
#         bp.rot = rot_to_blender(Quaternion(b.local_rot))

#         bone_props[b.name] = bp

#     if not len(bone_props):
#         return get_edit_bones_props()

#     return bone_props
