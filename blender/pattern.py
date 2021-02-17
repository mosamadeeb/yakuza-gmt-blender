from typing import Dict, List

import bpy
from bpy.types import Action, ActionGroup, Panel, Preferences
from mathutils import Vector
from yakuza_gmt.blender.bone_props import (get_edit_bones_props,
                                           get_gmd_bones_props)
from yakuza_gmt.blender.coordinate_converter import convert_gmt_to_blender
from yakuza_gmt.blender.error import GMTError
from yakuza_gmt.blender.pattern_lists import *
from yakuza_gmt.read import read_gmt_file_from_data
from yakuza_gmt.read_gmd import read_gmd_bones_from_data
from yakuza_gmt.structure.bone import find_bone
from yakuza_gmt.structure.curve import Curve
from yakuza_gmt.structure.types.format import get_curve_properties
from yakuza_gmt.yakuza_par_py.src import *


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


def import_curve(c: Curve, action: Action, group_name: str, head: Vector, parent_head: Vector):
    if not c.data_path:
        c.data_path = get_curve_properties(c.curve_format)
    if c.data_path == "":
        return
    values = convert_gmt_to_blender(c)
    if "location" in c.data_path:
        for v in range(len(values[0])):
            vs = [(x[v] - head[v]) + parent_head[v] for x in values]

            fcurve = action.fcurves.new(data_path=(
                f'pose.bones["{group_name}"].{c.data_path}'), index=v, action_group=group_name)
            fcurve.keyframe_points.add(len(c.graph.keyframes))
            fcurve.keyframe_points.foreach_set(
                "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
            fcurve.update()
    elif "rotation_quaternion" in c.data_path:
        for v in range(len(values[0])):
            vs = [x[v] for x in values]

            fcurve = action.fcurves.new(data_path=(
                f'pose.bones["{group_name}"].{c.data_path}'), index=v, action_group=group_name)
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

        for p, g, fl, bl, v in zip(pars, gmds, FILE_NAME_LISTS, HAND_BONES_LISTS, ["old", "new", "de"]):
            if not p:
                continue
            par = read_par(p)

            heads = get_edit_bones_props()
            if g:
                bone_par = read_par(p)
                gmd = bone_par.get_file("c_am_bone.gmd")
                if gmd:
                    heads = get_gmd_bones_props(
                        read_gmd_bones_from_data(decompress_file(gmd)))

            for i in range(len(fl)):
                file = par.get_file(fl[i])
                if not file:
                    continue
                gmt = read_gmt_file_from_data(decompress_file(file))
                for b in bl:
                    bone, _ = find_bone(b, gmt.bones)
                    if not bone:
                        continue
                    head, parent = heads[bone.name.string()]
                    parent_head = heads.get(parent)
                    if parent_head:
                        parent_head = parent_head[0]
                    else:
                        parent_head = Vector()

                    group = groups.get(f"{b}_{v}")
                    for curve in bone.curves:
                        import_curve(curve, action, group.name,
                                     head, parent_head)

    except GMTError as error:
        print(str(error))
        print("Unable to read Pattern pars. Make sure the paths set in the addon preferences are correct.")


def make_pattern_groups(action: Action) -> Dict[str, ActionGroup]:
    groups = dict()
    for bl, v in zip(HAND_BONES_LISTS, ["old", "new", "de"]):
        for b in bl:
            groups[f"{b}_{v}"] = action.groups.new(f"{b}_{v}")

    return groups


def make_pattern_action() -> Action:
    preferences = bpy.context.preferences
    addon_prefs = preferences.addons["yakuza_gmt"].preferences

    pattern_action = bpy.data.actions.new("GMT_Pattern")
    groups = make_pattern_groups(pattern_action)
    make_pattern_curves(pattern_action, groups, addon_prefs)

    return pattern_action


def set_pattern_drivers(curve, pattern_action, version):
    pass
