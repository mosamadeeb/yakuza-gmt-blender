from copy import deepcopy
from typing import Dict, Tuple

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import FCurve, Operator
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix, Quaternion, Vector

from ..gmt_lib import *
from ..read_cmt import *
from .bone_props import GMTBlenderBoneProps, get_edit_bones_props
from .coordinate_converter import (pattern_from_blender, pos_from_blender,
                                   rot_from_blender)
from .error import GMTError


class ExportGMT(Operator, ExportHelper):
    """Exports an animation to the GMT format"""
    bl_idname = "export_scene.gmt"
    bl_label = "Export Yakuza GMT"

    filter_glob: StringProperty(default="*.gmt", options={"HIDDEN"})

    filename_ext = '.gmt'

    def action_callback(self, context: bpy.context):
        items = []

        action_name = ""
        ao = context.active_object
        if ao and ao.animation_data:
            # Add the selected action first so that it's the default value
            selected_action = ao.animation_data.action
            if selected_action:
                action_name = selected_action.name
                items.append((action_name, action_name, ""))

        for a in [act for act in bpy.data.actions if act.name != action_name]:
            items.append((a.name, a.name, ""))
        return items

    def armature_callback(self, context):
        items = []
        ao = context.active_object
        ao_name = ao.name

        if ao and ao.type == 'ARMATURE':
            # Add the selected armature first so that it's the default value
            items.append((ao_name, ao_name, ""))

        for a in [arm for arm in bpy.data.objects if arm.type == 'ARMATURE' and arm.name != ao_name]:
            items.append((a.name, a.name, ""))
        return items

    def action_update(self, context):
        name = self.action_name
        if '[' in name and ']' in name:
            # used to avoid suffixes (e.g ".001")
            self.gmt_file_name = name[name.index('[')+1:name.index(']')]
            self.gmt_anm_name = name[:name.index('[')]

    action_name: EnumProperty(
        items=action_callback,
        name="Action",
        description="The action to be exported",
        update=action_update)

    armature_name: EnumProperty(
        items=armature_callback,
        name="Armature",
        description="The armature used for the action")

    gmt_game: EnumProperty(
        items=[('KENZAN', 'Ryu Ga Gotoku Kenzan', ""),
               ('YAKUZA_3', 'Yakuza 3, 4, Dead Souls', ""),
               ('YAKUZA_5', 'Yakuza 5', ""),
               ('ISHIN', 'Yakuza 0, Kiwami, Ishin, FOTNS', ""),
               ('DE', 'Dragon Engine (Yakuza 6, Kiwami 2, Like a Dragon, ...)', "")],
        name="Game Preset",
        description="Target game which the exported GMT will be used in",
        default=3)

    gmt_file_name: StringProperty(
        name="GMT File Name",
        description="Internal GMT file name",
        maxlen=30)

    gmt_anm_name: StringProperty(
        name="GMT Animation Name",
        description="Internal GMT animation name",
        maxlen=30)

    split_vector_curves: BoolProperty(
        name='Split Vector',
        description='Splits vector_c_n animation from center_c_n, to more closely match game behavior. '
                    'Will clear existing vector_c_n animation from the action.\n'
                    'Does not affect Y3-5 animations',
        default=True
    )

    is_auth: BoolProperty(
        name='Is Auth/Hact',
        description='Specify the animation\'s origin.\n'
                    'If this is enabled, then the animation should be from hact.par or auth folder. '
                    'Otherwise, it will be treated as being from motion folder.\n'
                    'Needed for proper vector splitting for Y0/K1.\n'
                    'Does not affect Y3-Y5 or DE. Does not affect anything if Split Vector is disabled',
        default=False
    )

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = True  # No animation.

        layout.prop(self, 'armature_name')
        layout.prop(self, 'action_name')
        layout.separator()
        layout.prop(self, 'gmt_file_name')
        layout.prop(self, 'gmt_anm_name')
        layout.separator()
        layout.prop(self, 'gmt_game')

        vector_col = layout.column()
        vector_col.prop(self, 'split_vector_curves')

        is_auth_row = vector_col.row()
        is_auth_row.prop(self, 'is_auth')

        is_auth_row.enabled = self.split_vector_curves and self.gmt_game == 'ISHIN'
        vector_col.enabled = self.gmt_game in ['ISHIN', 'DE']

        # update file and anm name if both are empty
        if self.gmt_file_name == self.gmt_anm_name == "":
            self.action_update(context)

    def execute(self, context):
        import time

        try:
            arm = self.check_armature(context)
            if isinstance(arm, str):
                raise GMTError(arm)

            start_time = time.time()
            exporter = GMTExporter(context, self.filepath, self.as_keywords(ignore=("filter_glob",)))
            exporter.export()

            elapsed_s = "{:.2f}s".format(time.time() - start_time)
            print("GMT export finished in " + elapsed_s)

            self.report({"INFO"}, f"Finished exporting {exporter.action_name}")
            return {'FINISHED'}
        except GMTError as error:
            print("Catching Error")
            self.report({"ERROR"}, str(error))
        return {'CANCELLED'}

    def check_armature(self, context: bpy.context):
        """Sets the active object to be the armature chosen by the user"""

        if self.armature_name:
            armature = bpy.data.objects.get(self.armature_name)
            if armature:
                context.view_layer.objects.active = armature
                return 0

        # check the active object first
        ao = context.active_object
        if ao and ao.type == 'ARMATURE' and ao.data.bones[:]:
            return 0

        # if the active object isn't a valid armature, get its collection and check

        if ao:
            collection = ao.users_collection[0]
        else:
            collection = context.view_layer.active_layer_collection

        if collection and collection.name != 'Master Collection':
            meshObjects = [o for o in bpy.data.collections[collection.name].objects
                           if o.data in bpy.data.meshes[:] and o.find_armature()]

            armatures = [a.find_armature() for a in meshObjects]
            if meshObjects:
                armature = armatures[0]
                if armature.data.bones[:]:
                    context.view_layer.objects.active = armature
                    return 0

        return "No armature found to get animation from"


class GMTExporter:
    def __init__(self, context: bpy.context, filepath, export_settings: Dict):
        self.filepath = filepath
        self.context = context

        # used for bone translation before exporting
        self.action_name = export_settings.get("action_name")
        self.gmt_anm_name = export_settings.get("gmt_anm_name")
        self.gmt_game = export_settings.get("gmt_game")
        self.split_vector_curves = export_settings.get("split_vector_curves")
        self.is_auth = export_settings.get("is_auth")

        gmt_file_name = export_settings.get("gmt_file_name")

        # self.start_frame = export_settings.get("start_frame")  # convenience
        # self.end_frame = export_settings.get("end_frame")  # convenience
        # self.interpolation = export_settings.get("interpolation")  # manual interpolation if needed
        # # auth or motion, for converting center/vector pos
        # self.gmt_context = export_settings.get("gmt_context")

        # Important: to update the vector version properly, scale bone has to be added after creating the animation
        self.gmt = GMT(gmt_file_name, GMTVersion[self.gmt_game] if self.gmt_game != 'DE' else GMTVersion.ISHIN)

    bone_props: Dict[str, GMTBlenderBoneProps]

    def export(self):
        print(f"Exporting action: {self.action_name}")

        # Active object was set correctly during operator execution
        self.ao = self.context.active_object
        if not self.ao or self.ao.type != 'ARMATURE':
            raise GMTError('Armature not found')

        self.bone_props = get_edit_bones_props(self.ao)

        # Export a single animation
        # GMTs with multiple animations are not supported for now
        self.gmt.animation = self.make_anm(self.action_name)
        write_gmt_to_file(self.gmt, self.filepath)

        print("GMT Export finished")

    def make_anm(self, action_name) -> GMTAnimation:
        action = bpy.data.actions.get(action_name)

        if not action:
            raise GMTError('Action not found')

        # Framerate apparently does not affect anything, and end frame is unused
        anm = GMTAnimation(self.gmt_anm_name, 30.0, 0)

        if self.gmt.version == GMTVersion.ISHIN and self.gmt_game != 'DE':
            # Add scale bone for Y0/K1
            scale_bone = GMTBone('scale')
            scale_bone.location = GMTCurve.new_location_curve()
            scale_bone.rotation = GMTCurve.new_rotation_curve()
            anm.bones['scale'] = scale_bone

        for group in action.groups.values():
            anm.bones[group.name] = self.make_bone(group.name, group.channels)

        # Try splitting vector from center
        if self.split_vector_curves and self.gmt_game in ['ISHIN', 'DE']:
            split_vector(anm.bones.get('center_c_n'), anm.bones.get('vector_c_n'), GMTVectorVersion.DRAGON_VECTOR if (
                self.gmt_game == 'DE') else GMTVectorVersion.OLD_VECTOR, self.is_auth)

        return anm

    def make_bone(self, bone_name: str, channels: List[FCurve]) -> GMTBone:
        bone = GMTBone(bone_name)

        loc_len, rot_len = 0, 0
        loc_curves, rot_curves, pat1_curves = dict(), dict(), dict()

        for c in channels:
            if "location" in c.data_path[c.data_path.rindex(".") + 1:]:
                if loc_len == 0:
                    loc_len = len(c.keyframe_points)
                elif loc_len != len(c.keyframe_points):
                    # TODO: Add an option to fill channels (by default) when there are unmatching keyframes
                    raise GMTError(f"FCurve {c.data_path} has channels with unmatching keyframes")

                if c.array_index == 0:
                    loc_curves["x"] = c
                elif c.array_index == 1:
                    loc_curves["y"] = c
                elif c.array_index == 2:
                    loc_curves["z"] = c

            elif "rotation_quaternion" in c.data_path[c.data_path.rindex(".") + 1:]:
                if rot_len == 0:
                    rot_len = len(c.keyframe_points)
                elif rot_len != len(c.keyframe_points):
                    raise GMTError(f"FCurve {c.data_path} has channels with unmatching keyframes")

                if c.array_index == 0:
                    rot_curves["w"] = c
                elif c.array_index == 1:
                    rot_curves["x"] = c
                elif c.array_index == 2:
                    rot_curves["y"] = c
                elif c.array_index == 3:
                    rot_curves["z"] = c

            elif "pat1" in c.data_path:
                if c.data_path[c.data_path.rindex(".") + 1:] == "pat1_left_hand":
                    pat1_curves["left_" + str(c.array_index)] = c
                elif c.data_path[c.data_path.rindex(".") + 1:] == "pat1_right_hand":
                    pat1_curves["right_" + str(c.array_index)] = c

        # Location curves
        if len(loc_curves) == 3:
            bone.location = self.make_curve([loc_curves[k] for k in sorted(loc_curves.keys())],
                                            GMTCurveType.LOCATION, GMTCurveChannel.ALL, bone_name)
        elif len(loc_curves) == 1:
            k = loc_curves.keys()[0]

            if k == 'x':
                channel = GMTCurveChannel.X
            elif k == 'y':
                channel = GMTCurveChannel.Y
            elif k == 'z':
                channel = GMTCurveChannel.Z

            bone.location = self.make_curve(loc_curves[k], GMTCurveType.LOCATION, channel, bone_name)
        else:
            print(f'Warning: Invalid number of location channels for bone {bone_name} - skipping...')

        # Rotation curves
        if len(rot_curves) == 4:
            bone.rotation = self.make_curve([rot_curves[k] for k in sorted(rot_curves.keys())],
                                            GMTCurveType.ROTATION, GMTCurveChannel.ALL, bone_name)
        elif len(rot_curves) == 2 and 'w' in rot_curves:
            k = [c for c in rot_curves.keys() if c != 'w'][0]

            if k == 'x':
                channel = GMTCurveChannel.XW
            elif k == 'y':
                channel = GMTCurveChannel.YW
            elif k == 'z':
                channel = GMTCurveChannel.ZW

            bone.rotation = self.make_curve([rot_curves['w'], rot_curves[k]], GMTCurveType.ROTATION, channel, bone_name)
        else:
            print(f'Warning: Invalid number of rotation channels for bone {bone_name} - skipping...')

        # Patterns
        pattern_hand_curves = []
        for pat in pat1_curves:
            if 'left' in pat:
                channel = GMTCurveChannel.LEFT_HAND
            elif 'right' in pat:
                channel = GMTCurveChannel.RIGHT_HAND

            pattern_hand_curves.append(self.make_curve(
                [pat1_curves[pat]], GMTCurveType.PATTERN_HAND, channel, bone_name))

        if len(pattern_hand_curves):
            bone.patterns_hand = pattern_hand_curves

        return bone

    def make_curve(self, fcurves: List[FCurve], curve_type: GMTCurveType, channel: GMTCurveChannel, bone_name: str) -> GMTCurve:
        # fcurves contains either of the following, each in the represented order:
        #   x, y, z location channels
        #   one location channel
        #   w, x, y, z rotation channels
        #   w channel + one rotation channel
        #   one pattern channel

        if curve_type == GMTCurveType.LOCATION:
            channel_count = 3 if (channel == GMTCurveChannel.ALL) else 1
        elif curve_type == GMTCurveType.ROTATION:
            channel_count = 4 if (channel == GMTCurveChannel.ALL) else 2
        elif curve_type == GMTCurveType.PATTERN_HAND:
            channel_count = 1

        axes_co = []
        for i in range(channel_count):
            axis_co = [0] * 2 * len(fcurves[i].keyframe_points)
            fcurves[i].keyframe_points.foreach_get("co", axis_co)
            axes_co.append(axis_co)

        keyframes = axes_co[0][::2]
        channel_values = [co[1:][::2] for co in axes_co]

        # Interpolation, if any, should be done here, before the keyframes are created

        # if interpolate:
        #     # Apply constant interpolation by duplicating keyframes
        #     pol = [True] * len(fcurves[axes[0]].keyframe_points)
        #     axis_pol = pol.copy()
        #     for axis in axes:
        #         fcurves[axis].keyframe_points.foreach_get(
        #             "interpolation", axis_pol)
        #         pol = list(map(lambda a, b: a and (b == 0),
        #                        pol, axis_pol))  # 'CONSTANT' = 0

        #     j = 0
        #     for i in range(len(pol) - 1):
        #         k = i + j
        #         if pol[i] and curve.graph.keyframes[k + 1] - curve.graph.keyframes[k] > 1:
        #             curve.values.insert(k + 1, curve.values[k])
        #             curve.graph.keyframes.insert(
        #                 k + 1, curve.graph.keyframes[k + 1] - 1)
        #             j += 1

        curve = GMTCurve(curve_type, channel)
        curve.keyframes = list(map(lambda f: GMTKeyframe(int(f), None), keyframes))

        # interpolate = True
        if curve_type == GMTCurveType.LOCATION:
            if channel_count == 3:
                converted_values = self.transform_location(bone_name, list(map(
                    lambda x, y, z: Vector((x, y, z)),
                    channel_values[0],
                    channel_values[1],
                    channel_values[2]
                )))

            elif channel_count == 1:
                # Convert values as whole vectors, then change channel
                # TODO: maybe export single channel if possible (when all values are single channel)?
                # TODO: maybe allow receiving intermediate channel counts to this function (2 for loc, 3 for rot)?
                if channel == GMTCurveChannel.X:
                    vecs = list(map(lambda v: Vector((v, 0.0, 0.0)), channel_values[0]))
                elif channel == GMTCurveChannel.Y:
                    vecs = list(map(lambda v: Vector((0.0, v, 0.0)), channel_values[0]))
                elif channel == GMTCurveChannel.Z:
                    vecs = list(map(lambda v: Vector((0.0, 0.0, v)), channel_values[0]))

                converted_values = self.transform_location(bone_name, vecs)
                channel = GMTCurveChannel.ALL

        elif curve_type == GMTCurveType.ROTATION:
            if channel_count == 4:
                converted_values = self.transform_rotation(bone_name, list(map(
                    lambda w, x, y, z: Quaternion((w, x, y, z)),
                    channel_values[0],
                    channel_values[1],
                    channel_values[2],
                    channel_values[3],
                )))

            elif channel_count == 2:
                if channel == GMTCurveChannel.XW:
                    quats = list(map(lambda w, v: Quaternion((w, v, 0.0, 0.0)), channel_values[0], channel_values[1]))
                elif channel == GMTCurveChannel.YW:
                    quats = list(map(lambda w, v: Quaternion((w, 0.0, v, 0.0)), channel_values[0], channel_values[1]))
                elif channel == GMTCurveChannel.ZW:
                    quats = list(map(lambda w, v: Quaternion((w, 0.0, 0.0, v)), channel_values[0], channel_values[1]))

                converted_values = self.transform_location(bone_name, quats)
                channel = GMTCurveChannel.ALL

        elif curve_type == GMTCurveType.PATTERN_HAND:
            if channel_count == 1:
                converted_values = channel_values[0]

                if self.gmt_game != 'DE':
                    # Prevent pattern numbers larger than old engine max to be exported
                    converted_values = self.correct_pattern(converted_values)

                converted_values = list(map(lambda s, e: [int(s), int(e)], *pattern_from_blender(converted_values)))

        # Assign the values
        for kf, val in zip(curve.keyframes, converted_values):
            kf.value = val

        return curve

    def correct_pattern(self, pattern):
        return list(map(lambda x: 0 if x > 17 else x, pattern))

    def transform_location(self, bone_name: str, values: List[Vector]) -> List[Tuple[float]]:
        prop = self.bone_props[bone_name]
        head = prop.head

        parent_head = self.bone_props.get(prop.parent_name)
        if parent_head:
            parent_head = parent_head.head
        else:
            parent_head = Vector()

        loc = prop.loc
        rot = prop.rot

        pre_mat = (
            rot.to_matrix().to_4x4()
            @ Matrix.Translation(loc)
        )

        post_mat = (
            Matrix.Translation(loc).inverted()
            @ rot.to_matrix().to_4x4().inverted()
        )

        values = list(map(lambda x: pos_from_blender((
            pre_mat
            @ Matrix.Translation(x)
            @ post_mat
        ).to_translation() + head - parent_head), values))

        return values

    def transform_rotation(self, bone_name: str, values: List[Quaternion]) -> List[Tuple[float]]:
        prop = self.bone_props[bone_name]

        parent_rot = self.bone_props.get(prop.parent_name)
        if parent_rot:
            parent_rot = parent_rot.rot_local
        else:
            parent_rot = Quaternion()

        loc = prop.loc
        rot = prop.rot
        rot_local = prop.rot_local

        pre_mat = (
            # rot_local.to_matrix().to_4x4().inverted()
            rot.to_matrix().to_4x4()
            # @ parent_rot.to_matrix().to_4x4()
            @ Matrix.Translation(loc)
        )

        post_mat = (
            Matrix.Translation(loc).inverted()
            @ parent_rot.to_matrix().to_4x4().inverted()
            @ rot.to_matrix().to_4x4().inverted()
            @ rot_local.to_matrix().to_4x4()  # .inverted()
        )

        values = list(map(lambda x: rot_from_blender((
            pre_mat
            @ x.to_matrix().to_4x4()
            @ post_mat
        ).to_quaternion()), values))

        return values


def split_vector(center_bone: GMTBone, vector_bone: GMTBone, vector_version: GMTVectorVersion, is_auth: bool):
    """Splits vector_c_n curves from center_c_n for proper conversion.
    Does not affect NO_VECTOR animations.
    """

    if vector_version == GMTVectorVersion.NO_VECTOR or not (center_bone and vector_bone):
        return

    # in GMT coordinate system:
    # OLD_VECTOR and is_auth -> vector should copy X and Z of center, and have a 0 Y channel
    # OLD_VECTOR and not is_auth -> vector should be used for X and Z of center, center should have Y only
    # DRAGON_VECTOR -> vector should be used instead of center, center should be empty
    # Rotation should be copied to vector in all cases, and should be removed from center in all cases except (OLD_VECTOR and is_auth)

    vector_bone.location = deepcopy(center_bone.location)
    vector_bone.rotation = deepcopy(center_bone.rotation)

    if vector_version == GMTVectorVersion.OLD_VECTOR:
        # Clear Y channel in vector location
        if vector_bone.location.channel == GMTCurveChannel.ALL:
            for kf in vector_bone.location.keyframes:
                kf.value = (kf.value[0], 0.0, kf.value[2])

        elif vector_bone.location.channel == GMTCurveChannel.Y:
            vector_bone.location.keyframes.clear()
            vector_bone.location.keyframes.append(GMTKeyframe(0, (0.0)))

        if not is_auth:
            # Clear X and Z channels in center location
            if center_bone.location.channel == GMTCurveChannel.ALL:
                for kf in center_bone.location.keyframes:
                    kf.value = (0.0, kf.value[1], 0.0)

            elif center_bone.location.channel == GMTCurveChannel.X or center_bone.location.channel == GMTCurveChannel.Z:
                center_bone.location.keyframes.clear()
                center_bone.location.keyframes.append(GMTKeyframe(0, (0.0)))

            # Clear center rotation
            center_bone.rotation = GMTCurve.new_rotation_curve()

    elif vector_version == GMTVectorVersion.DRAGON_VECTOR:
        center_bone.location = GMTCurve.new_location_curve()
        center_bone.rotation = GMTCurve.new_rotation_curve()


def menu_func_export(self, context):
    self.layout.operator(ExportGMT.bl_idname, text='Yakuza Animation (.gmt)')
