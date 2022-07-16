from copy import deepcopy
from typing import Dict, List

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Action, FCurve, Operator
from bpy_extras.io_utils import ExportHelper
from mathutils import Quaternion, Vector

from ..gmt_lib import *
from ..gmt_lib.gmt.gmt_writer import write_cmt_to_file, write_ifa_to_file
from ..gmt_lib.gmt.structure.cmt import *
from ..gmt_lib.gmt.structure.ifa import *
from .bone_props import GMTBlenderBoneProps, get_edit_bones_props
from .coordinate_converter import (convert_cmt_anm_from_blender,
                                   pattern1_from_blender,
                                   pattern2_from_blender,
                                   transform_location_from_blender,
                                   transform_rotation_from_blender)
from .error import GMTError


class ExportGMT(Operator, ExportHelper):
    """Exports an animation to the GMT format"""
    bl_idname = "export_scene.gmt"
    bl_label = "Export Yakuza GMT"

    filter_glob: StringProperty(default="*.gmt;*.cmt;*.ifa", options={"HIDDEN"})

    # Don't force a file extension
    filename_ext = '.gmt'
    check_extension = None

    def export_format_update(self, context: bpy.context):
        # Change the file extension
        for screenArea in context.window.screen.areas:
            if screenArea.type == 'FILE_BROWSER':
                params = screenArea.spaces[0].params
                if len(params.filename) > 3 and params.filename[-4] == '.':
                    params.filename = params.filename[:-3] + self.export_format.lower()
                else:
                    params.filename += '.' + self.export_format.lower()
                break

    def action_callback(self, context: bpy.context):
        items = []

        # TODO: Instead of setting the default action to the one used by the active object,
        # maybe we should use the one used by the selected armature_name?
        action_name = ""
        ao = context.active_object if self.export_format != 'CMT' else context.scene.camera
        if ao and ao.animation_data:
            # Add the selected action first so that it's the default value
            selected_action = ao.animation_data.action
            if selected_action:
                action_name = selected_action.name
                items.append((action_name, action_name, ""))

        for a in [act for act in bpy.data.actions if act.name != action_name]:
            items.append((a.name, a.name, ""))
        return items

    def armature_callback(self, context: bpy.context):
        items = []

        if self.export_format == 'CMT':
            ao = context.scene.camera
            obj_type = 'CAMERA'
        else:
            ao = context.active_object
            obj_type = 'ARMATURE'

        ao_name = ao.name if ao else ''

        if ao and ao.type == obj_type:
            # Add the selected armature first so that it's the default value
            items.append((ao_name, ao_name, ""))

        for a in [arm for arm in bpy.data.objects if arm.type == obj_type and arm.name != ao_name]:
            items.append((a.name, a.name, ""))
        return items

    def action_update(self, context: bpy.context):
        name = self.action_name
        if '[' in name and ']' in name:
            # Used to avoid suffixes (e.g ".001")
            self.gmt_file_name = name[name.index('[')+1:name.index(']')]
            self.gmt_anm_name = name[:name.index('[')]

            # Set the file name to be the same as the internal gmt file name
            for screenArea in context.window.screen.areas:
                if screenArea.type == 'FILE_BROWSER':
                    params = screenArea.spaces[0].params
                    params.filename = f'{self.gmt_file_name}.{self.export_format.lower()}'
                    break

    export_format: EnumProperty(
        items=[('GMT', 'GMT (Model Animation)', ''),
               ('CMT', 'CMT (Camera Animation)', ''),
               ('IFA', 'IFA (Pre-Ishin Face Animation)', ''),
               ],
        name="Export Format",
        description="The animation format to export as",
        default=0,
        update=export_format_update
    )

    action_name: EnumProperty(
        items=action_callback,
        name="Action",
        description="The action to be exported",
        default=0,
        update=action_update)

    armature_name: EnumProperty(
        items=armature_callback,
        name="Armature",
        description="The armature which the action will use as a base")

    gmt_game: EnumProperty(
        items=[('KENZAN', 'Ryu Ga Gotoku Kenzan', ""),
               ('YAKUZA3', 'Yakuza 3, 4, Dead Souls', ""),
               ('YAKUZA5', 'Yakuza 5', ""),
               ('ISHIN', 'Yakuza 0, Kiwami, Ishin, FOTNS', ""),
               ('DE', 'Dragon Engine (Yakuza 6, Kiwami 2, ...)', ""),
               ],
        name="Game Preset",
        description="Target game which the exported GMT will be used in",
        default=3)

    cmt_game: EnumProperty(
        items=[('KENZAN', 'Ryu Ga Gotoku Kenzan', ""),
               ('YAKUZA3', 'Yakuza 3, 4, Dead Souls', ""),
               ('YAKUZA5', 'Yakuza 5 or newer (0, Kiwami, Dragon Engine, ...)', ""),
               ],
        name="Game Preset",
        description="Target game which the exported CMT will be used in",
        default=2)

    use_camera_keyframes: BoolProperty(
        name='Export Camera Data Keyframes',
        description='If enabled, will export keyframes animated in the camera object if they exist. '
                    'Otherwise, will export the keyframes from the action only.\n'
                    'If this option is enabled and both channels exist, an error will occur. '
                    'To fix it, one of the channels should be deleted',
        default=True
    )

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

        layout.prop(self, 'export_format')
        layout.separator()
        layout.prop(self, 'armature_name')
        layout.prop(self, 'action_name')
        layout.separator()

        if self.export_format == 'GMT':
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

            # Update file and anm name if both are empty
            if self.gmt_file_name == self.gmt_anm_name == "":
                self.action_update(context)
        elif self.export_format == 'CMT':
            layout.prop(self, 'cmt_game')
            layout.separator()
            layout.prop(self, 'use_camera_keyframes')

        self.export_format_update(context)

    def execute(self, context):
        import time

        try:
            if self.export_format == 'CMT':
                exporter_cls = CMTExporter
            else:
                arm = self.check_armature(context)
                if isinstance(arm, str):
                    raise GMTError(arm)

                exporter_cls = IFAExporter if self.export_format == 'IFA' else GMTExporter

            start_time = time.time()
            exporter = exporter_cls(context, self.filepath, self.as_keywords(ignore=("filter_glob",)))
            exporter.export()

            elapsed_s = "{:.2f}s".format(time.time() - start_time)
            print("Export finished in " + elapsed_s)

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

        self.action_name = export_settings.get("action_name")
        self.gmt_anm_name = export_settings.get("gmt_anm_name")
        self.gmt_game = export_settings.get("gmt_game")
        self.split_vector_curves = export_settings.get("split_vector_curves")
        self.is_auth = export_settings.get("is_auth")

        gmt_file_name = export_settings.get("gmt_file_name")

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

        # Framerate only affects motion GMTs (not auth/hacts), and end frame is unused
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

        loc_curves, rot_curves, pat1_curves, pat_other_curves = (dict() for _ in range(4))

        loc_axes = ('x', 'y', 'z')
        rot_axes = ('w',) + loc_axes
        for c in channels:
            # Data path without bone name
            data_path = c.data_path[c.data_path.rindex('.') + 1:]

            if data_path == 'location' and (0 <= c.array_index < 3):
                loc_curves[loc_axes[c.array_index]] = c

            elif data_path == 'rotation_quaternion' and (0 <= c.array_index < 4):
                rot_curves[rot_axes[c.array_index]] = c

            elif data_path.startswith('pat1'):
                pat1_curves[data_path] = c

            elif data_path.startswith('pat'):
                pat_other_curves[data_path] = c

            else:
                print(f'Warning: Ignoring curve with unsupported data path {c.data_path} and index {c.array_index}')

        # Location curves
        if 0 < len(loc_curves) <= 3:
            bone.location = self.make_curve([loc_curves[k] for k in sorted(loc_curves.keys())],
                                            GMTCurveType.LOCATION, GMTCurveChannel.ALL, bone_name)

        # Rotation curves
        if 0 < len(rot_curves) <= 4:
            bone.rotation = self.make_curve([rot_curves[k] for k in sorted(rot_curves.keys())],
                                            GMTCurveType.ROTATION, GMTCurveChannel.ALL, bone_name)

        # Patterns (hand)
        pattern_hand_curves = []
        for pat in pat1_curves:
            if 'left' in pat:
                channel = GMTCurveChannel.LEFT_HAND
            elif 'right' in pat:
                channel = GMTCurveChannel.RIGHT_HAND
            else:
                channel = GMTCurveChannel(int(pat.split('_')[-1]))

            pattern_hand_curves.append(self.make_curve(
                [pat1_curves[pat]], GMTCurveType.PATTERN_HAND, channel, bone_name))

        if len(pattern_hand_curves):
            bone.patterns_hand = pattern_hand_curves

        # Patterns (unk and face)
        pattern_unk_curves = []
        pattern_face_curves = []
        for pat in pat_other_curves:
            pat_type = GMTCurveType.PATTERN_UNK if ('pat2' in pat) else GMTCurveType.PATTERN_FACE
            channel = GMTCurveChannel(int(pat.split('_')[-1]))

            curve = self.make_curve([pat_other_curves[pat]], pat_type, channel, bone_name)

            if pat_type == GMTCurveType.PATTERN_UNK:
                pattern_unk_curves.append(curve)
            else:
                pattern_face_curves.append(curve)

        if len(pattern_unk_curves):
            bone.patterns_unk = pattern_unk_curves

        if len(pattern_face_curves):
            bone.patterns_face = pattern_face_curves

        return bone

    def make_curve(self, fcurves: List[FCurve], curve_type: GMTCurveType, channel: GMTCurveChannel, bone_name: str) -> GMTCurve:
        # fcurves contains either of the following, each in the represented order:
        #   x, y, z location channels (1-3 curves)
        #   w, x, y, z rotation channels (1-4 curves)
        #   one pattern channel

        channel_count = len(fcurves)
        channel_indices = list(map(lambda c: c.array_index, fcurves))

        # axes_co = []
        keyframes_dict = dict()
        for i in range(channel_count):
            axis_co = [0] * 2 * len(fcurves[i].keyframe_points)
            fcurves[i].keyframe_points.foreach_get('co', axis_co)

            keyframes_dict.update(dict.fromkeys(axis_co[::2]))
            # axis_co_iter = iter(axis_co)
            # axes_co.append(zip(axis_co_iter, axis_co_iter))

        keyframes: List[float] = sorted(keyframes_dict)

        channel_values = []
        for i in range(channel_count):
            channel_values.append(list(map(lambda k: fcurves[i].evaluate(k), keyframes)))

        # Alternative code for fixing unmatching keyframes
        # Was made in case using fcurve.evaluate is slow, but it turns out it isn't
        # for i, k in enumerate(keyframes):
        #     keyframes_dict[k] = i

        # for x, co in enumerate(axes_co):
        #     values = [None] * len(keyframes_dict)

        #     # Set all existing keyframes
        #     for k, v in co:
        #         values[keyframes_dict[k]] = v

        #     # Evaluate all missing frames
        #     for i in range(len(values)):
        #         if values[i] is None:
        #             values[i] = fcurves[x].evaluate(keyframes[i])

        #     channel_values.append(values)

        if curve_type == GMTCurveType.LOCATION:
            if channel_count != 3:
                if (bone := self.ao.pose.bones.get(bone_name)) is None:
                    raise GMTError(f'Could not fix unmatching keyframes for {bone_name}')

                for i in [x for x in range(3) if x not in channel_indices]:
                    channel_values.insert(i, [bone.location[i]] * len(keyframes))

            converted_values = transform_location_from_blender(self.bone_props, bone_name, list(map(
                lambda x, y, z: Vector((x, y, z)),
                channel_values[0],
                channel_values[1],
                channel_values[2]
            )))

            # Check if there are any completely zero channels
            empties = list(map(lambda i: all(map(lambda x: x[i] == 0.0, converted_values)), range(3)))

            # If at least two channels are empty, change the channel type and update the values
            if empties.count(True) >= 2:
                # If no channels are non-empty, choose X
                i = empties.index(False) if False in empties else 0

                converted_values = list(map(lambda v: (v[i],), converted_values))
                channel = (GMTCurveChannel.X, GMTCurveChannel.Y, GMTCurveChannel.Z)[i]

        elif curve_type == GMTCurveType.ROTATION:
            if channel_count != 4:
                if (bone := self.ao.pose.bones.get(bone_name)) is None:
                    raise GMTError(f'Could not fix unmatching keyframes for {bone_name}')

                for i in [x for x in range(4) if x not in channel_indices]:
                    channel_values.insert(i, [bone.rotation_quaternion[i]] * len(keyframes))

            converted_values = transform_rotation_from_blender(self.bone_props, bone_name, list(map(
                lambda w, x, y, z: Quaternion((w, x, y, z)),
                channel_values[0],
                channel_values[1],
                channel_values[2],
                channel_values[3],
            )))

            # Check if there are any completely zero channels (from x, y, z only)
            empties = list(map(lambda i: all(map(lambda x: x[i] == 0.0, converted_values)), range(3)))

            # If at least two channels are empty, change the channel type and update the values
            if empties.count(True) >= 2:
                # If no channels are non-empty, choose X
                i = empties.index(False) if False in empties else 0

                # v[3] is w channel
                converted_values = list(map(lambda v: (v[i], v[3]), converted_values))
                channel = (GMTCurveChannel.XW, GMTCurveChannel.YW, GMTCurveChannel.ZW)[i]

        elif curve_type == GMTCurveType.PATTERN_HAND:
            converted_values = channel_values[0]

            if self.gmt_game != 'DE':
                # Prevent pattern numbers larger than old engine max to be exported
                converted_values = self.correct_pattern(converted_values)

            converted_values = list(map(lambda s, e: [int(s), int(e)], *pattern1_from_blender(converted_values)))
        elif curve_type in (GMTCurveType.PATTERN_UNK, GMTCurveType.PATTERN_FACE):
            converted_values = list(map(lambda v: [int(v)], pattern2_from_blender(channel_values[0])))

        # Create the GMTCurve after finalizing all changes to the FCurves
        curve = GMTCurve(curve_type, channel)
        curve.keyframes = list(map(lambda f, v: GMTKeyframe(int(f), v), keyframes, converted_values))

        return curve

    def correct_pattern(self, pattern):
        return list(map(lambda x: 0 if x > 17 else x, pattern))


class CMTExporter:
    def __init__(self, context: bpy.context, filepath, export_settings: Dict):
        self.filepath = filepath
        self.context = context

        self.action_name = export_settings.get('action_name')
        self.cmt_game = export_settings.get('cmt_game')
        self.use_camera_keyframes = export_settings.get('use_camera_keyframes')

        self.camera = bpy.data.objects.get(export_settings.get('armature_name'))
        if not self.camera:
            raise GMTError('No camera to export animation from')

    def export(self):
        print(f"Exporting action: {self.action_name}")

        self.cmt = CMT(CMTVersion[self.cmt_game])

        # Only single animation export for now
        self.cmt.animation = self.make_anm(self.action_name)
        write_cmt_to_file(self.cmt, self.filepath)

        print("CMT Export finished")

    def make_anm(self, action_name):
        action = bpy.data.actions.get(action_name)
        cam_action: Action = (anm_data := self.camera.data.animation_data) and anm_data.action

        if not action:
            raise GMTError('Action not found')

        anm = CMTAnimation()

        # Combined max frame range
        frame_count = 1 + int(max(action.frame_range[1], cam_action.frame_range[1] if cam_action else 0))

        loc_curves = [action.fcurves.find('location', index=x) for x in range(3)]
        rot_curves = [action.fcurves.find('rotation_quaternion', index=x) for x in range(4)]

        loc_list = self.export_fcurves(loc_curves, 'location', frame_count)
        rot_list = self.export_fcurves(rot_curves, 'rotation_quaternion', frame_count)

        data_values = dict.fromkeys(['lens', 'dof.focus_distance', 'clip_start', 'clip_end'])

        for datapath in data_values:
            curve = action.fcurves.find(f'data.{datapath}')
            cam_curve = cam_action and cam_action.fcurves.find(datapath)

            if self.use_camera_keyframes and cam_curve:
                if curve:
                    raise GMTError(f'Multiple sources for camera datapath \"{datapath}\" exist. Delete one of the channels or disable \"Export Camera Data Keyframes\"')

                curve = cam_curve

            data_values[datapath] = self.export_fcurves([curve], f'data.{datapath}', frame_count)

        fov_list = data_values['lens']
        dist_list = data_values['dof.focus_distance']
        clip_start_list = data_values['clip_start']
        clip_end_list = data_values['clip_end']

        if has_clip_range := (clip_start_list or clip_end_list):
            if not clip_start_list:
                clip_start_list = [0.1] * frame_count
            if not clip_end_list:
                clip_end_list = [10000.0] * frame_count

        frames = anm.frames = [None] * frame_count
        for i in range(frame_count):
            frame = frames[i] = CMTFrame(loc_list[i], fov_list[i])
            frame.from_dist_rotation(dist_list[i], rot_list[i], True)

            if has_clip_range:
                frame.clip_range = (clip_start_list[i], clip_end_list[i])

        # Convert the CMT frames after exporting everything
        convert_cmt_anm_from_blender(anm, self.camera.data)
        return anm

    def export_fcurves(self, fcurves: List[FCurve], datapath, frame_count):
        fcurves = [x for x in fcurves if x]

        channel_count = len(fcurves)
        channel_indices = list(map(lambda c: c.array_index, fcurves))

        channel_values = []
        for i in range(channel_count):
            channel_values.append(list(map(lambda k: fcurves[i].evaluate(k), range(frame_count))))

        if datapath == 'location':
            if channel_count != 3:
                for i in [x for x in range(3) if x not in channel_indices]:
                    channel_values.insert(i, [self.camera.location[i]] * frame_count)

            return list(map(lambda x, y, z: Vector((x, y, z)), *channel_values))
        elif datapath == 'rotation_quaternion':
            if channel_count != 4:
                for i in [x for x in range(3) if x not in channel_indices]:
                    channel_values.insert(i, [self.camera.rotation_quaternion[i]] * frame_count)

            return list(map(lambda w, x, y, z: Quaternion((w, x, y, z)), *channel_values))
        else:
            # Single channels only
            if not channel_values:
                if datapath in ('data.clip_start', 'data.clip_end'):
                    return list()

                return [self.camera.path_resolve(datapath)] * frame_count

            return channel_values[0]


class IFAExporter(GMTExporter):
    def __init__(self, context: bpy.context, filepath, export_settings: Dict):
        self.filepath = filepath
        self.context = context

        self.action_name = export_settings.get("action_name")

    def export(self):
        print(f"Exporting action: {self.action_name}")

        # Active object was set correctly during operator execution
        self.ao = self.context.active_object
        if not self.ao or self.ao.type != 'ARMATURE':
            raise GMTError('Armature not found')

        if not (face_bone := self.ao.pose.bones.get('face')):
            raise GMTError('Face bone not found')

        self.bone_props = get_edit_bones_props(self.ao)
        self.face_children = list(map(lambda x: x.name, face_bone.children_recursive))

        self.ifa = IFA(self.make_bone_list())
        write_ifa_to_file(self.ifa, self.filepath)

        print("IFA Export finished")

    def make_bone_list(self):
        action = bpy.data.actions.get(self.action_name)

        if not action:
            raise GMTError('Action not found')

        bone_list = list()
        for group in [x for x in action.groups if x.name in self.face_children]:
            gmt_bone = self.make_bone(group.name, group.channels)

            has_location = gmt_bone.location and len(gmt_bone.location.keyframes)
            has_rotation = gmt_bone.rotation and len(gmt_bone.rotation.keyframes)

            if not (has_location and has_rotation):
                print(f'Warning: Ignoring bone due to missing animation: {group.name}')
                continue

            bone = IFABone(group.name, self.bone_props[group.name].parent_name)

            gmt_bone.location.fill_channels()
            bone.location = gmt_bone.location.keyframes[0].value

            gmt_bone.rotation.fill_channels()
            bone.rotation = gmt_bone.rotation.keyframes[0].value

            bone_list.append(bone)

        return bone_list


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
            vector_bone.location.keyframes.append(GMTKeyframe(0, (0.0,)))

        if not is_auth:
            # Clear X and Z channels in center location
            if center_bone.location.channel == GMTCurveChannel.ALL:
                for kf in center_bone.location.keyframes:
                    kf.value = (0.0, kf.value[1], 0.0)

            elif center_bone.location.channel == GMTCurveChannel.X or center_bone.location.channel == GMTCurveChannel.Z:
                center_bone.location.keyframes.clear()
                center_bone.location.keyframes.append(GMTKeyframe(0, (0.0,)))

            # Clear center rotation
            center_bone.rotation = GMTCurve.new_rotation_curve()

    elif vector_version == GMTVectorVersion.DRAGON_VECTOR:
        center_bone.location = GMTCurve.new_location_curve()
        center_bone.rotation = GMTCurve.new_rotation_curve()


def menu_func_export(self, context):
    self.layout.operator(ExportGMT.bl_idname, text='Yakuza Animation (.gmt/.cmt/.ifa)')
