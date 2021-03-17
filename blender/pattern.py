from typing import Dict, List, Tuple

import bpy
from bpy.types import Action, ActionGroup, FCurve, Panel, Preferences
from mathutils import Quaternion, Vector

from ..read import read_gmt_file_from_data
from ..read_gmd import read_gmd_bones_from_data
from ..structure.bone import find_bone
from ..structure.curve import Curve, new_pos_curve, new_rot_curve
from ..structure.types.format import get_curve_properties
from ..yakuza_par_py.src import *
from .bone_props import get_edit_bones_props, get_gmd_bones_props
from .coordinate_converter import convert_gmt_to_blender
from .error import GMTError
from .pattern_lists import *


class PatternBasePanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and context.active_pose_bone and "pattern" in context.active_pose_bone.name


class PatternPanel(PatternBasePanel, Panel):
    """Creates a Panel in the Object properties window"""

    bl_idname = "POSEBONE_PT_pattern"
    bl_label = "Pattern Properties"

    def draw(self, context):
        layout = self.layout

        active_pose_bone = context.active_pose_bone
        layout.prop(active_pose_bone, 'pat1_left_hand')
        layout.prop(active_pose_bone, 'pat1_right_hand')


class PatternIndicesPanel(PatternBasePanel, Panel):
    bl_idname = "POSEBONE_PT_pattern_indices"
    bl_parent_id = "POSEBONE_PT_pattern"
    bl_label = "Pattern Indices"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        box = layout.grid_flow(columns=2)
        for i in range(27):
            if i < 15:
                text = f"({HAND_PATTERN[i][3]}) {HAND_PATTERN[i][1]}"
            elif i < 19:
                text = f"({i-1}) {HAND_PATTERN[i][1]} - [DE] {HAND_PATTERN_DE[i][1]}"
            else:
                text = f"({i-1}) [DE] {HAND_PATTERN_DE[i][1]}"

            if i == 9:
                text += " [Y3-4 end]"
            elif i == 14:
                text += " [Y5 end]"
            elif i == 21:
                text += " [K2 end]"
            elif i == 25:
                text += " [JE end]"
            elif i == 26:
                text += " [Y7 end]"

            box.label(text=text)


def import_curve_from_pattern(c: Curve, action: Action, pattern_index: int, group_name: str, head: Vector, parent_head: Vector):
    if not c.data_path:
        c.data_path = get_curve_properties(c.curve_format)
    if c.data_path == "":
        return
    values = convert_gmt_to_blender(c)
    if "location" in c.data_path:
        for v in range(len(values[0])):
            vs = [(x[v] - head[v]) + parent_head[v] for x in values]

            fcurve = action.fcurves.new(data_path=(
                f'pose.bones["{group_name}_{pattern_index}"].{c.data_path}'), index=v, action_group=group_name)
            fcurve.keyframe_points.add(len(c.graph.keyframes))
            fcurve.keyframe_points.foreach_set(
                "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
            fcurve.update()
    elif "rotation_quaternion" in c.data_path:
        for v in range(len(values[0])):
            vs = [x[v] for x in values]

            fcurve = action.fcurves.new(data_path=(
                f'pose.bones["{group_name}_{pattern_index}"].{c.data_path}'), index=v, action_group=group_name)
            fcurve.keyframe_points.add(len(c.graph.keyframes))
            fcurve.keyframe_points.foreach_set(
                "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
            fcurve.update()


def make_pattern_curves(action: Action, groups: Dict[str, ActionGroup], prefs: Preferences) -> None:
    try:
        path_list = []
        for paths in [["old_par", "new_par", "dragon_par"], ["old_bone_par", "new_bone_par", "dragon_bone_par"]]:
            for p in paths:
                path_list.append(prefs.get(p))

        pars, gmds = path_list[:3], path_list[3:]

        for p, g, fl, bl, v in zip(pars, gmds, FILE_NAME_LISTS, HAND_BONES_LISTS, VERSION_STR):
            if not p:
                continue
            par = read_par(p)

            heads = get_edit_bones_props()
            if g:
                bone_par = read_par(g)
                gmd = bone_par.get_file("c_am_bone.gmd")
                if gmd:
                    heads = get_gmd_bones_props(
                        read_gmd_bones_from_data(decompress_file(gmd)))

            for i in range(len(fl)):
                file = par.get_file(fl[i])
                if not file:
                    for b in bl:
                        group = groups.get(f"{b}{v}")
                        import_curve_from_pattern(
                            new_pos_curve(), action, i, group.name, Vector(), Vector())
                        import_curve_from_pattern(
                            new_rot_curve(), action, i, group.name, Vector(), Vector())
                    continue
                gmt = read_gmt_file_from_data(decompress_file(file))
                for b in bl:
                    group = groups.get(f"{b}{v}")

                    bone, _ = find_bone(b, gmt.bones)
                    if not bone:
                        import_curve_from_pattern(
                            new_pos_curve(), action, i, group.name, Vector(), Vector())
                        import_curve_from_pattern(
                            new_rot_curve(), action, i, group.name, Vector(), Vector())
                        continue

                    head, parent = heads[bone.name.string()]
                    parent = heads.get(parent)
                    parent_head = parent[0] if parent else Vector()

                    for curve in bone.curves:
                        import_curve_from_pattern(curve, action, i, group.name,
                                                  head, parent_head)

    except GMTError as error:
        print(str(error))
        print("Unable to read Pattern pars. Make sure the paths set in the addon preferences are correct.")


def make_pattern_groups(action: Action) -> Dict[str, ActionGroup]:
    groups = dict()
    for bl, v in zip(HAND_BONES_LISTS, VERSION_STR):
        for b in bl:
            groups[f"{b}{v}"] = action.groups.new(f"{b}{v}")

    return groups


def make_pattern_action() -> Action:
    preferences = bpy.context.preferences
    addon_prefs = preferences.addons["yakuza_gmt"].preferences

    pattern_action = bpy.data.actions.new("GMT_Pattern")
    groups = make_pattern_groups(pattern_action)
    make_pattern_curves(pattern_action, groups, addon_prefs)

    return pattern_action


def get_pattern_frames(p_curve: FCurve, frame: float) -> Tuple[int, int, float]:
    start = [k for k in p_curve.keyframe_points if k.co[0] <= frame]

    if not len(start):
        return (-1, -1, 0)

    s = start[-1].co[0]
    p1 = int(start[-1].co[1])

    end = [k for k in p_curve.keyframe_points if k.co[0] > frame]

    if not end:
        return (p1, p1, 0)

    e = end[0].co[0]
    p2 = int(end[0].co[1])

    f = (frame - s) / (e - s)

    return (p1, p2, f)


def evaluate_location(p1: int, p2: int, f: float, c: List[FCurve]) -> Vector:
    p1_v = []
    p2_v = []
    for i in range(p1*7, p1*7 + 3):
        p1_v.append(c[i].keyframe_points[0].co[1])
    for i in range(p2*7, p2*7 + 3):
        p2_v.append(c[i].keyframe_points[0].co[1])

    v1 = Vector(p1_v)
    v2 = Vector(p2_v)
    return v1.lerp(v2, f)


def evaluate_rotation_quaternion(p1: int, p2: int, f: float, c: List[FCurve]) -> Quaternion:
    p1_v = []
    p2_v = []
    for i in range(p1*7 + 3, p1*7 + 7):
        p1_v.append(c[i].keyframe_points[0].co[1])
    for i in range(p2*7 + 3, p2*7 + 7):
        p2_v.append(c[i].keyframe_points[0].co[1])

    q1 = Quaternion(p1_v)
    q2 = Quaternion(p2_v)
    return q1.slerp(q2, f)


@bpy.app.handlers.persistent
def apply_patterns(scene):
    frame = scene.frame_current
    pattern_action = bpy.data.actions.get("GMT_Pattern")
    if not pattern_action:
        return

    for collection in bpy.data.collections:
        for object in [o for o in collection.objects if o.animation_data and o.animation_data.action]:
            action = object.animation_data.action

            pattern_c_n = action.groups.get("pattern_c_n")
            version = 1
            if not pattern_c_n:
                pattern_c_n = action.groups.get("pattern_n")
                version = 0
                if not pattern_c_n:
                    continue

            if version == 1 and object.pose.bones.get("koyu0_r_n"):
                version = 2

            pl_curve = None
            pr_curve = None
            for pat in [c for c in pattern_c_n.channels if "pat1" in c.data_path]:
                if pat.data_path.endswith("pat1_left_hand"):
                    pl_curve = pat
                elif pat.data_path.endswith("pat1_right_hand"):
                    pr_curve = pat

            p1l = p1r = p2l = p2r = fl = fr = -1
            if pl_curve:
                p1l, p2l, fl = get_pattern_frames(pl_curve, frame)
            if pr_curve:
                p1r, p2r, fr = get_pattern_frames(pr_curve, frame)

            if p1l == p1r == -1 or p2l == p2r == -1:
                # TODO: reset the bones to -1 state or leave as is?
                continue

            for b in HAND_BONES_LISTS[version]:
                bone = object.pose.bones.get(b)
                group = pattern_action.groups.get(b + VERSION_STR[version])
                if not bone or not group:
                    continue
                p1, p2 = -1, -1
                if b.endswith("_l") or "_l_" in b:
                    p1, p2, f = p1l, p2l, fl
                elif b.endswith("_r") or "_r_" in b:
                    p1, p2, f = p1r, p2r, fr

                if p1 == -1 or p2 == -1:
                    # TODO: reset the bones to -1 state or leave as is?
                    continue

                # ignore pattern values greater than the currently loaded patterns
                if p1*7 + 7 > len(group.channels) or p2*7 + 7 > len(group.channels):
                    continue

                bone.location = evaluate_location(p1, p2, f, group.channels)
                bone.rotation_quaternion = evaluate_rotation_quaternion(
                    p1, p2, f, group.channels)
