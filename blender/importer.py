from copy import deepcopy
from math import tan
from os.path import basename
from typing import Dict

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Action, Operator
from bpy_extras.io_utils import ImportHelper
from mathutils import Euler, Quaternion, Vector

from ..gmt_lib import *
from ..read_cmt import CMTAnimation, CMTData, CMTFile, read_cmt_file
from .bone_props import GMTBlenderBoneProps, get_edit_bones_props
from .coordinate_converter import (convert_gmt_curve_to_blender,
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

    filter_glob: StringProperty(default="*.gmt;*.cmt", options={"HIDDEN"})

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
            start_time = time.time()
            if self.filepath.endswith('.cmt'):
                importer = CMTImporter(context, self.filepath, self.as_keywords(ignore=("filter_glob",)))
                importer.read()
            else:
                arm = self.check_armature(context)
                if isinstance(arm, str):
                    raise GMTError(arm)

                importer = GMTImporter(context, self.filepath, self.as_keywords(ignore=("filter_glob",)))
                importer.read()

            elapsed_s = "{:.2f}s".format(time.time() - start_time)
            print("GMT import finished in " + elapsed_s)

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


class CMTImporter:
    def __init__(self, context: bpy.context, filepath, import_settings: Dict):
        self.filepath = filepath
        self.context = context

    cmt_file: CMTFile

    def read(self):
        self.cmt_file = read_cmt_file(self.filepath)
        if type(self.cmt_file) is str:
            raise GMTError(self.cmt_file)

        self.animate_camera()

    def animate_camera(self):
        camera = self.context.scene.camera

        if not camera:
            camera_data = bpy.data.cameras.new(name='Camera')
            camera = bpy.data.objects.new('Camera', camera_data)
            self.context.scene.collection.objects.link(camera)

        if not camera.animation_data:
            camera.animation_data_create()

        camera.rotation_mode = 'QUATERNION'
        camera.data.lens_unit = 'MILLIMETERS'
        camera.data.sensor_fit = 'VERTICAL'
        camera.data.sensor_height = 100.0

        #sensor_diag = sqrt((camera.data.sensor_width ** 2 + camera.data.sensor_height ** 2))

        for anm in self.cmt_file.animations:
            frame_count = anm.frame_count
            camera.animation_data.action = bpy.data.actions.new(name=self.cmt_file.name)
            action = camera.animation_data.action

            group = action.groups.new("camera")

            anm.anm_data = self.convert_cam_to_blender(anm.anm_data)

            locations, rotations, foc_lengths = [], [], []
            for data in anm.anm_data:
                pos = Vector((data.pos_x, data.pos_y, data.pos_z))
                foc = Vector((data.foc_x, data.foc_y, data.foc_z))
                locations.append(pos)

                #foc_len = (foc - pos).length * 1000
                """
                if data.fov == 0.0:
                    print("ZERO FOV")
                if tan(data.fov / 2) == 0.0:
                    print("ZERO TAN")
                """
                foc_len = (camera.data.sensor_height / 2) / tan(data.fov / 2)
                foc_lengths.append(foc_len)

            rotations = self.get_cam_rotations(anm)

            frames = list(iter(range(anm.frame_count)))

            for i in range(3):
                loc = [x[i] for x in locations]
                location = action.fcurves.new(data_path=(
                    'location'), index=i, action_group=group.name)
                location.keyframe_points.add(anm.frame_count)
                location.keyframe_points.foreach_set(
                    "co", [x for co in zip(frames, loc) for x in co])
                location.update()
            for i in range(4):
                rot = [x[i] for x in rotations]
                rotation = action.fcurves.new(
                    data_path=('rotation_quaternion'), index=i, action_group=group.name)
                rotation.keyframe_points.add(anm.frame_count)
                rotation.keyframe_points.foreach_set(
                    "co", [x for co in zip(frames, rot) for x in co])
                rotation.update()

            angle = action.fcurves.new(data_path=(
                'data.lens'), action_group=group.name)
            angle.keyframe_points.add(anm.frame_count)
            angle.keyframe_points.foreach_set(
                "co", [x for co in zip(frames, foc_lengths) for x in co])
            angle.update()

        self.context.scene.frame_start = 0
        self.context.scene.frame_current = 0
        self.context.scene.frame_end = frame_count

    def get_cam_rotations(self, anm: CMTAnimation):
        rotations = []
        for data in anm.anm_data:
            pos = Vector((data.pos_x, data.pos_y, data.pos_z))
            foc = Vector((data.foc_x, data.foc_y, data.foc_z))

            # Yes, i'm leaving this c++ code here until the CMT importer is 100% functional
            """
            public static Quaternion LookAt(Vector3 sourcePoint, Vector3 destPoint)
            {
                Vector3 forwardVector = Vector3.Normalize(destPoint - sourcePoint);

                float dot = Vector3.Dot(Vector3.forward, forwardVector);

                if (Math.Abs(dot - (-1.0f)) < 0.000001f)
                {
                    return new Quaternion(Vector3.up.x, Vector3.up.y, Vector3.up.z, 3.1415926535897932f);
                }
                if (Math.Abs(dot - (1.0f)) < 0.000001f)
                {
                    return Quaternion.identity;
                }

                float rotAngle = (float)Math.Acos(dot);
                Vector3 rotAxis = Vector3.Cross(Vector3.forward, forwardVector);
                rotAxis = Vector3.Normalize(rotAxis);
                return CreateFromAxisAngle(rotAxis, rotAngle);
            }

            // just in case you need that function also
            public static Quaternion CreateFromAxisAngle(Vector3 axis, float angle)
            {
                float halfAngle = angle * .5f;
                float s = (float)System.Math.Sin(halfAngle);
                Quaternion q;
                q.x = axis.x * s;
                q.y = axis.y * s;
                q.z = axis.z * s;
                q.w = (float)System.Math.Cos(halfAngle);
                return q;
            }
            """

            forward = (foc - pos).normalized()
            """
            axis = Vector((0, 0, -1)).cross(forward).normalized()
            #if axis.magnitude == 0.0:
            #    axis = Vector((0, 1, 0))
            
            dot = Vector((0, 0, -1)).dot(forward)
            if abs(dot - (-1.0)) < 0.000001:
                rotations.append((pi, axis.x, axis.y, axis.z))
                continue
            if abs(dot - (1.0)) < 0.000001:
                rotations.append(Quaternion())
                continue
            angle = acos(dot)
            print(f"angle: {angle}")
            print(f"data.rot: {data.rot}")
            rotations.append((angle, axis.x, axis.y, axis.z))
            """
            bpy.ops.transform.rotate()
            rotation = forward.to_track_quat('-Z', 'Y')
            rotation = rotation @ Euler((0, 0, data.rot)).to_quaternion()
            # rotation.rotate()
            rotations.append(rotation)

            # v0 not working
            """
            pos = Vector((data.pos_x, data.pos_y, data.pos_z))
            pos_f = Vector((data.foc_x, data.foc_y, data.foc_z))
            axis = pos_f - pos
            axis.normalize()
            rotations.append((data.rot, axis.x, axis.y, axis.z))
            """

        return rotations

    def convert_cam_to_blender(self, data_list: CMTData):
        for data in data_list:
            data.pos_x = -data.pos_x
            pos_z = data.pos_y
            pos_y = data.pos_z
            data.pos_y = pos_y
            data.pos_z = pos_z

            data.foc_x = -data.foc_x
            foc_z = data.foc_y
            foc_y = data.foc_z
            data.foc_y = foc_y
            data.foc_z = foc_z

        return data_list


class GMTImporter:
    def __init__(self, context: bpy.context, filepath, import_settings: Dict):
        self.filepath = filepath
        self.context = context
        self.merge_vector_curves = import_settings.get('merge_vector_curves')
        self.is_auth = import_settings.get('is_auth')

    gmt: GMT

    def read(self):
        # try:
        self.gmt = read_gmt(self.filepath)
        self.make_actions()
        # except Exception as e:
        #     raise GMTError(f'{e}')

    def make_actions(self):
        ao = self.context.active_object

        print(f'Importing file: {self.gmt.name}')

        if not ao.animation_data:
            ao.animation_data_create()

        hidden = ao.hide_get()
        mode = ao.mode

        # necessary steps to ensure proper importing
        ao.hide_set(False)
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.transforms_clear()
        bpy.ops.pose.select_all(action='DESELECT')

        bone_props = get_edit_bones_props(ao)

        bpy.ops.object.mode_set(mode=mode)
        ao.hide_set(hidden)

        vector_version = self.gmt.vector_version

        end_frame = 1
        frame_rate = 30
        for anm in self.gmt.animation_list:
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
                    import_curve(self.context, curve, bone_name, action, group.name, bone_props)

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
    self.layout.operator(ImportGMT.bl_idname, text='Yakuza Animation (.gmt/.cmt)')
