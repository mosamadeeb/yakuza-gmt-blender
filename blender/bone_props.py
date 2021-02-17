from typing import Dict, Tuple

import bpy
from mathutils import Vector
from yakuza_gmt.blender.coordinate_converter import pos_to_blender


def get_edit_bones_props() -> Dict[str, Tuple[Vector, str]]:
    ao = bpy.context.active_object
    heads = {}
    bpy.ops.object.mode_set(mode='EDIT')
    for b in ao.data.edit_bones:
        parent_name = b.parent.name if b.parent else ""
        if "head_no_rot" in b:
            heads[b.name] = (Vector(b["head_no_rot"].to_list()), parent_name)
        else:
            heads[b.name] = (b.head, parent_name)
    bpy.ops.object.mode_set(mode='POSE')
    return heads


def get_gmd_bones_props(gmd_bones) -> Dict[str, Tuple[Vector, str]]:
    heads = {}
    for b in gmd_bones:
        parent_name = b.parent_recursive[0].name if len(
            b.parents_recursive) else ""
        heads[b.name] = (pos_to_blender(Vector(b.global_pos[:3])), parent_name)

    if not len(heads):
        return get_edit_bones_props()

    return heads
