from copy import deepcopy
from os.path import basename
from typing import Dict

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Action, Operator
from bpy_extras.io_utils import ImportHelper
from mathutils import Quaternion, Vector

from ..gmt_lib import *
from ..gmt_lib.gmt.gmt_reader import read_cmt, read_ifa
from ..gmt_lib.gmt.structure.cmt import *
from ..gmt_lib.gmt.structure.ifa import *
from .bone_props import GMTBlenderBoneProps, get_edit_bones_props
from .coordinate_converter import (convert_cmt_anm_to_blender,
                                   convert_gmt_curve_to_blender,
                                   pattern1_to_blender, pattern2_to_blender,
                                   transform_location_to_blender,
                                   transform_rotation_to_blender)
from .error import GMTError

# from .pattern import make_pattern_action
# from .pattern_lists import VERSION_STR


class ImportGMT(Operator, ImportHelper):
    """Loads a GMT file into blender"""
    bl_idname = "import_scene.gmt"
    bl_label = "Import Yakuza GMT"

    filter_glob: StringProperty(default="*.gmt;*.cmt;*.ifa", options={"HIDDEN"})

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

    armature_name: EnumProperty(
        items=armature_callback,
        name='Target Armature',
        description='The armature to use as a base for importing the animation. '
                    'This armature should be from a GMD from the same game as the animation'
    )

    merge_vector_curves: BoolProperty(
        name='Merge Vector',
        description='Merges vector_c_n animation into center_c_n, to allow for easier editing/previewing.\n'
                    'This option should not be disabled. Does not affect Y3-5 animations',
        default=True
    )

    is_auth: BoolProperty(
        name='Is Auth/Hact',
        description='Specify the animation\'s origin.\n'
                    'If this is enabled, then the animation should be from hact.par or auth folder. '
                    'Otherwise, it will be treated as being from motion folder.\n'
                    'Needed for proper vector merging for Y0/K1.\n'
                    'Does not affect Y3-Y5 or DE. Does not affect anything if Merge Vector is disabled',
        default=False
    )

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = True  # No animation.

        layout.prop(self, 'armature_name')
        layout.prop(self, 'merge_vector_curves')

        is_auth_row = layout.row()
        is_auth_row.prop(self, 'is_auth')
        is_auth_row.enabled = self.merge_vector_curves

    def execute(self, context):
        import time

        try:
            if self.filepath.endswith('.cmt'):
                importer_cls = CMTImporter
            else:
                arm = self.check_armature(context)
                if isinstance(arm, str):
                    raise GMTError(arm)

                importer_cls = IFAImporter if self.filepath.endswith('.ifa') else GMTImporter

            start_time = time.time()
            importer = importer_cls(context, self.filepath, self.as_keywords(ignore=("filter_glob",)))
            importer.read()

            elapsed_s = "{:.2f}s".format(time.time() - start_time)
            print("Import finished in " + elapsed_s)

            self.report({"INFO"}, f"Finished importing {basename(self.filepath)}")
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

        return "No armature found to add animation to"


def setup_armature(ao: bpy.types.Object) -> Dict[str, GMTBlenderBoneProps]:
    if not ao.animation_data:
        ao.animation_data_create()

    hidden = ao.hide_get()
    mode = ao.mode

    # Necessary steps to ensure proper importing
    ao.hide_set(False)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.transforms_clear()
    bpy.ops.pose.select_all(action='DESELECT')

    bone_props = get_edit_bones_props(ao)

    bpy.ops.object.mode_set(mode=mode)
    ao.hide_set(hidden)

    return bone_props


class IFAImporter:
    def __init__(self, context: bpy.context, filepath, import_settings: Dict):
        self.filepath = filepath
        self.context = context

    ifa: IFA

    def read(self):
        self.ifa = read_ifa(self.filepath)
        self.make_action()

    def make_action(self):
        ao = self.context.active_object

        bone_props = setup_armature(ao)

        action = ao.animation_data.action = bpy.data.actions.new(name=f'{basename(self.filepath)}')

        # Instead of rewriting the curve importing functions, we can just convert the IFA bones to GMT curves
        for bone in self.ifa.bone_list:
            group = action.groups.new(bone.name)

            for curve_values, curve_type in zip((bone.location, bone.rotation), (GMTCurveType.LOCATION, GMTCurveType.ROTATION)):
                curve = GMTCurve(curve_type)
                curve.keyframes.append(GMTKeyframe(0, curve_values))

                convert_gmt_curve_to_blender(curve)
                import_curve(self.context, curve, bone.name, action, group.name, bone_props)

        self.context.scene.frame_start = 0
        self.context.scene.frame_current = 0


class CMTImporter:
    def __init__(self, context: bpy.context, filepath, import_settings: Dict):
        self.filepath = filepath
        self.context = context

    cmt: CMT

    def read(self):
        self.cmt = read_cmt(self.filepath)
        self.animate_camera()

    def animate_camera(self):
        self.camera = self.context.scene.camera

        if not self.camera:
            camera_data = bpy.data.cameras.new(name='Camera')
            self.camera = bpy.data.objects.new('Camera', camera_data)
            self.context.scene.collection.objects.link(self.camera)

        if not self.camera.animation_data:
            self.camera.animation_data_create()

        # Set some properties that are needed for the imported action to look proper
        # While it might be possible to animate these, it will only complicate things
        self.camera.rotation_mode = 'QUATERNION'
        self.camera.data.lens_unit = 'MILLIMETERS'
        self.camera.data.sensor_fit = 'VERTICAL'
        self.camera.data.sensor_height = 100.0
        self.camera.data.dof.use_dof = True

        single = bool(self.cmt.animation)
        for i, anm in enumerate(self.cmt.animation_list):
            frame_rate = anm.frame_rate
            frame_count = len(anm.frames)
            self.make_action(anm, basename(self.filepath) + '' if single else f'({i})')

        self.context.scene.render.fps = int(frame_rate)
        self.context.scene.frame_start = 0
        self.context.scene.frame_current = 0
        self.context.scene.frame_end = frame_count

    def make_action(self, anm: CMTAnimation, action_name):
        action = self.camera.animation_data.action = bpy.data.actions.new(name=action_name)
        group = action.groups.new("Camera")

        # Convert the CMT frames before importing anything
        convert_cmt_anm_to_blender(anm, self.camera.data)
        dists, rotations = zip(*map(lambda x: x.to_dist_rotation(True), anm.frames))

        def import_curve(data_path, values):
            values = enumerate(zip(*values)) if hasattr(values[0], '__iter__') else [(-1, values)]

            for i, values_channel in values:
                fcurve = action.fcurves.new(data_path=data_path, index=i, action_group=group.name)
                fcurve.keyframe_points.add(len(values_channel))
                fcurve.keyframe_points.foreach_set('co', [x for co in zip(
                    range(len(values_channel)), values_channel) for x in co])

                fcurve.update()

        import_curve('location', list(map(lambda x: x.location[:], anm.frames)))
        import_curve('rotation_quaternion', list(map(lambda x: x[:], rotations)))
        import_curve('data.lens', list(map(lambda x: x.fov, anm.frames)))

        # Kenzan does not store the focus distance
        if self.cmt.version > CMTVersion.KENZAN:
            # TODO: This value for aperture_fstop is just an arbitrary value that gives a closer look to in-game DOF
            # This same fstop value should be used during animation or the resulting DOF in the game might look different
            import_curve('data.dof.focus_distance', dists)
            import_curve('data.dof.aperture_fstop', (15.0,))

        if anm.has_clip_range():
            # CMTs that were read from a file will either have a clip range for all frames, or no clip ranges at all
            clip_starts, clip_ends = zip(*map(lambda x: x.clip_range, anm.frames))
            import_curve('data.clip_start', clip_starts)
            import_curve('data.clip_end', clip_ends)


class GMTImporter:
    def __init__(self, context: bpy.context, filepath, import_settings: Dict):
        self.filepath = filepath
        self.context = context
        self.merge_vector_curves = import_settings.get('merge_vector_curves')
        self.is_auth = import_settings.get('is_auth')

    gmt: GMT

    def read(self):
        try:
            self.gmt = read_gmt(self.filepath)
            self.make_actions()
        except Exception as e:
            raise GMTError(f'{e}')

    def make_actions(self):
        print(f'Importing file: {self.gmt.name}')

        ao = self.context.active_object
        bone_props = setup_armature(ao)

        vector_version = self.gmt.vector_version

        end_frame = 1
        frame_rate = 30
        for anm in self.gmt.animation_list:
            anm_bone_props = dict() if (self.gmt.is_face_gmt and anm.is_face_anm()) else bone_props

            end_frame = max(end_frame, anm.end_frame)
            frame_rate = anm.frame_rate

            act_name = f'{anm.name}[{self.gmt.name}]'

            ao.animation_data.action = bpy.data.actions.new(name=act_name)
            action = ao.animation_data.action

            bones: Dict[str, GMTBone] = dict()
            for bone_name in anm.bones:
                if bone_name in ao.pose.bones:
                    bones[bone_name] = anm.bones[bone_name]
                else:
                    print(f'WARNING: Skipped bone: "{bone_name}"')

            # Convert curves early to allow for easier GMT modification before creating FCurves
            for bone_name in bones:
                for curve in bones[bone_name].curves:
                    convert_gmt_curve_to_blender(curve)

            # Try merging vector into center
            if self.merge_vector_curves:
                # Bone names are constant because vector does not exist pre-Ishin
                merge_vector(bones.get('center_c_n'), bones.get('vector_c_n'), vector_version, self.is_auth)

            for bone_name in bones:
                group = action.groups.new(bone_name)
                print(f'Importing ActionGroup: {group.name}')

                for curve in bones[bone_name].curves:
                    import_curve(self.context, curve, bone_name, action, group.name, anm_bone_props)

        # If pattern previewing is to be enabled later, this should be moved to the addon register function instead
        # Although that may require bone.par path in order to import the patterns with the basic skeleton GMDs
        # pattern_action = bpy.data.actions.get(f"GMT_Pattern{VERSION_STR[vector_version]}")
        # if not pattern_action and bpy.context.preferences.addons["yakuza_gmt"].preferences.get("use_patterns"):
        #     pattern_action = make_pattern_action(vector_version)

        self.context.scene.render.fps = int(frame_rate)
        self.context.scene.frame_start = 0
        self.context.scene.frame_current = 0
        self.context.scene.frame_end = int(end_frame)


def merge_vector(center_bone: GMTBone, vector_bone: GMTBone, vector_version: GMTVectorVersion, is_auth: bool):
    """Merges vector_c_n curves into center_c_n for easier modification.
    Does not affect NO_VECTOR animations.
    """

    if vector_version == GMTVectorVersion.NO_VECTOR or not (center_bone and vector_bone):
        return

    if (vector_version == GMTVectorVersion.OLD_VECTOR and not is_auth) or vector_version == GMTVectorVersion.DRAGON_VECTOR:
        # Both curves' values should be applied, so add vector to center
        center_bone.location = add_curve(center_bone.location, vector_bone.location, GMTCurveType.LOCATION)
        center_bone.rotation = add_curve(center_bone.rotation, vector_bone.rotation, GMTCurveType.ROTATION)

    # Reset vector's curves to avoid confusion, since it won't be used anymore
    vector_bone.location = GMTCurve.new_location_curve()
    vector_bone.rotation = GMTCurve.new_rotation_curve()
    convert_gmt_curve_to_blender(vector_bone.location)
    convert_gmt_curve_to_blender(vector_bone.rotation)


def add_curve(curve: GMTCurve, other: GMTCurve, expected_curve_type: GMTCurveType) -> GMTCurve:
    """Adds the animation data of a curve to this curve. Both curves need to have the same GMTCurveType.
    If their type is LOCATION, vectors will be added.
    If their type is ROTATION, quaternions will be multiplied.
    expected_curve_type is only used if both curves are None
    """

    if (other or curve) is None:
        if expected_curve_type == GMTCurveType.LOCATION:
            curve = GMTCurve.new_location_curve()
        elif expected_curve_type == GMTCurveType.ROTATION:
            curve = GMTCurve.new_rotation_curve()
        else:
            curve = GMTCurve(expected_curve_type)

        convert_gmt_curve_to_blender(curve)
        return curve
    elif other is None:
        return curve
    elif curve is None:
        return deepcopy(other)

    if curve.type != other.type:
        raise GMTError('Curves with different types cannot be added')

    if curve.type == GMTCurveType.LOCATION:
        # Vector add and lerp
        def add(v1, v2): return v1 + v2
        def lerp(v1, v2, f): return v1.lerp(v2, f)

        if len(curve.keyframes) == 0:
            curve.keyframes.append(GMTKeyframe(0, Vector()))
    elif curve.type == GMTCurveType.ROTATION:
        # Quaternion multiply and slerp
        def add(v1, v2): return v1 @ v2
        def lerp(v1, v2, f): return v1.slerp(v2, f)

        if len(curve.keyframes) == 0:
            curve.keyframes.append(GMTKeyframe(0, Quaternion()))
    else:
        raise GMTError(f'Incompatible curve type for addition: {curve.type}')

    result = list()
    curve_dict = {kf.frame: kf.value for kf in curve.keyframes}
    curve_min = curve.keyframes[0].frame
    curve_max = curve.keyframes[-1].frame

    other_dict = {kf.frame: kf.value for kf in other.keyframes}
    other_min = other.keyframes[0].frame
    other_max = other.keyframes[-1].frame

    # Iterate over frames from 0 to the last frame in either curve
    for i in range(max(curve.get_end_frame(), other.get_end_frame()) + 1):
        # Check if the current frame has a keyframe
        v1 = curve_dict.get(i)
        v2 = other_dict.get(i)

        # Do not add/interpolate if no values are explicitly specified in this frame
        if not (v1 is None and v2 is None):
            if v1 is None:
                # Get the last keyframe that is less than the current frame, or the first keyframe
                less = next((k for k in reversed(curve_dict) if k < i), curve_min)

                # Get the first keyframe that is greater than the current frame, or the last keyframe
                more = next((k for k in curve_dict if k > i), curve_max)

                # Interpolate between the two values for the current frame, or use the only value if there is only 1 keyframe
                v1 = lerp(curve_dict[less], curve_dict[more], (i - less) /
                          (more - less)) if less != more else curve_dict[less]
            if v2 is None:
                less = next((k for k in reversed(other_dict) if k < i), other_min)
                more = next((k for k in other_dict if k > i), other_max)
                v2 = lerp(other_dict[less], other_dict[more], (i - less) /
                          (more - less)) if less != more else other_dict[less]

            result.append(GMTKeyframe(i, add(v1, v2)))

    curve.keyframes = result
    return curve


def import_curve(context: bpy.context, curve: GMTCurve, bone_name: str, action: Action, group_name: str, bone_props: Dict[str, GMTBlenderBoneProps]):
    data_path = get_data_path_from_curve_type(context, curve.type, curve.channel)

    if data_path == '' or len(curve.keyframes) == 0:
        print(f'GMTWarning: Skipping type {curve.type} curve for {bone_name}...')
        return

    frames, values = zip(*map(lambda kf: (kf.frame, kf.value), curve.keyframes))

    need_const_interpolation = False
    if data_path == 'location':
        values = transform_location_to_blender(bone_props, bone_name, values)
    elif data_path == 'rotation_quaternion':
        values = transform_rotation_to_blender(bone_props, bone_name, values)
    elif 'pat1' in data_path:
        need_const_interpolation = True
        values = pattern1_to_blender(values)
    elif 'pat' in data_path:
        need_const_interpolation = True
        # pat2 and pat3 use the same format
        values = pattern2_to_blender(values)
    else:
        return

    for i, values_channel in enumerate(zip(*values)):
        fcurve = action.fcurves.new(data_path=(
            f'pose.bones["{bone_name}"].{data_path}'), index=i, action_group=group_name)
        fcurve.keyframe_points.add(len(frames))
        fcurve.keyframe_points.foreach_set('co', [x for co in zip(frames, values_channel) for x in co])

        # Not needed if the change_interpolation() handler is active
        if need_const_interpolation:
            for kf in fcurve.keyframe_points:
                kf.interpolation = 'CONSTANT'

        fcurve.update()


def get_data_path_from_curve_type(context: bpy.context, curve_type: GMTCurveType, curve_channel: GMTCurveChannel) -> str:
    if curve_type == GMTCurveType.LOCATION:
        return 'location'
    elif curve_type == GMTCurveType.ROTATION:
        return 'rotation_quaternion'
    elif curve_type == GMTCurveType.PATTERN_HAND:
        if curve_channel == GMTCurveChannel.LEFT_HAND:
            return 'pat1_left_hand'
        elif curve_channel == GMTCurveChannel.RIGHT_HAND:
            return 'pat1_right_hand'
        # GMTCurveChannel.UNK_HAND is not explicitly checked for since it's unknown if it's actually related to hands
        else:
            channel = curve_channel.value

            pat_tuple = (-32_768, 32_767, 0, f'pat1_unk_{channel}', f'Pat1 Unk {channel}', "Unknown pattern property")
            pat_string = '|'.join(map(lambda x: str(x), pat_tuple))

            # The type will be created, but it won't be added to the types dict (to be deleted) here
            # That will be taken care of in the unregister function of the addon
            return create_pose_bone_type(context, pat_string)
    elif curve_type in (GMTCurveType.PATTERN_UNK, GMTCurveType.PATTERN_FACE):
        channel = curve_channel.value

        # Both PATTERN_UNK and PATTERN_FACE use the same format, so just make the difference here
        pat_num = 2 if GMTCurveType.PATTERN_UNK else 3

        pat_tuple = (-128, 127, 0, f'pat{pat_num}_unk_{channel}',
                     f'Pat{pat_num} Unk {channel}', "Unknown pattern property")
        pat_string = '|'.join(map(lambda x: str(x), pat_tuple))

        return create_pose_bone_type(context, pat_string)
    else:
        return ''


def create_pose_bone_type(context: bpy.context, pat_string: str):
    # Example pat: '-1|25|-1|pat1_left_hand|Left Hand|some description'
    splits = pat_string.split('|', 5)

    if len(splits) != 6:
        print('GMTWarning: Unexpected pattern string when creating a PoseBone attribute')
        return ''

    min_val, max_val, default_val, prop_name, pat_name, desc = splits

    # Only set the attribute (and add it to the collection) if it was not created before
    if not hasattr(bpy.types.PoseBone, prop_name):
        if hasattr(context.scene, 'pattern_types'):
            pat = context.scene.pattern_types.add()
            pat.string = pat_string
        else:
            print('GMTWarning: Addon did not register correctly - missing collection property in scene')

        setattr(bpy.types.PoseBone, prop_name, bpy.props.IntProperty(name=pat_name, min=int(
            min_val), max=int(max_val), description=desc, default=int(default_val)))

    return prop_name


def menu_func_import(self, context):
    self.layout.operator(ImportGMT.bl_idname, text='Yakuza Animation (.gmt/.cmt/.ifa)')
