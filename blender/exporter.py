from typing import Dict
from copy import deepcopy

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector
from yakuza_gmt.blender.error import GMTError
from yakuza_gmt.read_cmt import *
from yakuza_gmt.structure.file import *
from yakuza_gmt.structure.version import GMTProperties
from yakuza_gmt.write import write_file


class ExportGMT(Operator, ExportHelper):
    """Loads a GMT file into blender"""
    bl_idname = "export_scene.gmt"
    bl_label = "Export Yakuza GMT"

    filter_glob: StringProperty(default="*.gmt", options={"HIDDEN"})

    filename_ext = '.gmt'

    # files: CollectionProperty(
    #    name="File Path",
    #    type=bpy.types.OperatorFileListElement,
    # )
    # Only allow importing one file at a time
    #file: StringProperty(name="File Path", subtype="FILE_PATH")

    def anm_callback(self, context):
        items = []
        for a in bpy.data.actions:
            items.append((a.name, a.name, ""))
        return items

    def skeleton_callback(self, context):
        items = []
        for a in bpy.data.armatures:
            items.append((a.name, a.name, ""))
        return items

    def get_file_name(self, context):
        name = self.anm_callback(context)[0][0]
        if "(" in name and ")" in name:
            # used to avoid suffixes (e.g ".001")
            return name[name.index("(")+1:name.index(")")]
        return ""

    def get_anm_name(self, context):
        name = self.anm_callback(context)[0][0]
        if "(" in name:
            return name[:name.index("(")]
        return ""

    anm_name: EnumProperty(
        items=anm_callback,
        name="Action",
        description="The action to be exported")

    skeleton_name: EnumProperty(
        items=skeleton_callback,
        name="Skeleton",
        description="The armature used for the action")

    gmt_properties: EnumProperty(
        items=[('KENZAN', 'Ryu Ga Gotoku Kenzan', ""),
               ('YAKUZA_3', 'Yakuza 3, 4, Dead Souls', ""),
               ('YAKUZA_5', 'Yakuza 5', ""),
               ('YAKUZA_0', 'Yakuza 0, Kiwami, Ishin, FOTNS', ""),
               ('YAKUZA_6', 'Yakuza 6, 7, Kiwami 2, Judgment', "")],
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

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = True  # No animation.

        layout.prop(self, 'anm_name')
        layout.prop(self, 'skeleton_name')
        layout.prop(self, 'gmt_properties')
        layout.prop(self, 'gmt_file_name')
        layout.prop(self, 'gmt_anm_name')

        self.gmt_file_name = self.get_file_name(context)
        self.gmt_anm_name = self.get_anm_name(context)

    def execute(self, context):
        arm = self.check_armature()
        if arm is str:
            self.report({"ERROR"}, arm)
            return {'CANCELLED'}

        try:
            exporter = GMTExporter(
                self.filepath, self.as_keywords(ignore=("filter_glob",)))
            exporter.export()

            self.report({"INFO"}, f"Finished exporting {exporter.anm_name}")
            return {'FINISHED'}
        except GMTError as error:
            print("Catching Error")
            self.report({"ERROR"}, str(error))
        return {'CANCELLED'}

    def check_armature(self):
        # check the active object first
        ao = bpy.context.active_object
        if ao and ao.type == 'ARMATURE' and ao.data.bones[:]:
            return 0

        # if the active object isn't a valid armature, get its collection and check

        if ao:
            collection = ao.users_collection[0]
        else:
            collection = bpy.context.view_layer.active_layer_collection

        meshObjects = [o for o in bpy.data.collections[collection.name].objects
                       if o.data in bpy.data.meshes[:] and o.find_armature()]

        armatures = [a.find_armature() for a in meshObjects]
        if meshObjects:
            armature = armatures[0]
            if armature.data.bones[:]:
                bpy.context.view_layer.objects.active = armature
                return 0

        return "No armature found to get animation from"


class GMTExporter:
    def __init__(self, filepath, export_settings: Dict):
        self.filepath = filepath
        # used for bone translation before exporting
        self.anm_name = export_settings.get("anm_name")
        self.gmt_file_name = export_settings.get("gmt_file_name")
        self.gmt_anm_name = export_settings.get("gmt_anm_name")
        self.skeleton_name = export_settings.get("skeleton_name")
        self.start_frame = export_settings.get("start_frame")  # convenience
        self.end_frame = export_settings.get("end_frame")  # convenience
        self.interpolation = export_settings.get(
            "interpolation")  # manual interpolation if needed
        self.gmt_properties = GMTProperties(
            export_settings.get("gmt_properties"))
        # auth or motion, for converting center/vector pos
        self.gmt_context = export_settings.get("gmt_context")

        self.gmt_file = GMTFile()

    def export(self):
        print(f"Exporting animation: {self.anm_name}")

        self.get_anm()
        self.format_header()
        with open(self.filepath, 'wb') as f:
            f.write(write_file(self.gmt_file, self.gmt_properties.version))

        print("GMT Export finished")

    def format_header(self):
        header = GMTHeader()

        header.big_endian = True
        header.version = self.gmt_properties.version
        header.file_name = Name(self.gmt_file_name)
        header.flags = 0

        self.gmt_file.header = header

    def get_anm(self):

        ao = bpy.context.active_object
        if not ao.animation_data:
            raise GMTError("No animation data found")

        action = bpy.data.actions.get(self.anm_name)

        anm = Animation()
        anm.name = Name(self.gmt_anm_name)
        anm.frame_rate = 30.0
        anm.index = anm.index1 = anm.index2 = anm.index3 = 0

        anm.bones = []

        self.setup_bone_locs()

        for group in action.groups.values():
            if group.name != "vector_c_n":
                anm.bones.append(self.make_bone(group.name, group.channels))
            else:
                center, c_index = find_bone("center_c_n", anm.bones)

                if not len(center.curves):
                    center_channels = [
                        c for c in group.channels if "gmt_" in c.data_path]

                    # Use vector head (0) because we already added center head once
                    center = self.make_bone(group.name, center_channels)
                    center.name = Name("center_c_n")

                    if c_index != -1:
                        anm.bones[c_index] = center
                    else:
                        anm.bones.insert(0, center)

                vector = self.make_bone(
                    group.name, [c for c in group.channels if "gmt_" not in c.data_path])
                anm.bones.append(vector)

                if self.gmt_properties.is_dragon_engine:
                    if not len(center.curves):
                        center.curves = [new_pos_curve(), new_rot_curve()]
                else:
                    vector_curves = deepcopy(vector.curves)
                    for c in vector.curves:
                        c = c.to_horizontal()

                    vertical = new_pos_curve()
                    if len(center.position_curves()):
                        vertical = center.position_curves()[0].to_vertical()

                    center.curves = vector_curves
                    for c in center.curves:
                        if 'POS' in c.curve_format.name:
                            c = add_curve(c, vertical)

                    # TODO: Move this to the converter once it's implemented
                    # Add scale bone to mark this gmt as non DE
                    scale = Bone()
                    scale.name = Name("scale")
                    scale.curves = [new_pos_curve(), new_rot_curve()]
                    anm.bones.insert(0, scale)

        self.gmt_file.animations = [anm]

    def make_bone(self, bone_name, channels) -> Bone:
        bone = Bone()
        bone.name = Name(bone_name)
        bone.curves = []

        loc_len, rot_len, pat1_len = 0, 0, 0
        loc_curves, rot_curves, pat1_curves = dict(), dict(), dict()

        for c in channels:
            if "location" in c.data_path[c.data_path.rindex(".") + 1:]:
                if loc_len == 0:
                    loc_len = len(c.keyframe_points)
                elif loc_len != len(c.keyframe_points):
                    raise GMTError(
                        f"FCurve {c.data_path} has channels with unmatching keyframes")

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
                    raise GMTError(
                        f"FCurve {c.data_path} has channels with unmatching keyframes")

                if c.array_index == 0:
                    rot_curves["w"] = c
                elif c.array_index == 1:
                    rot_curves["x"] = c
                elif c.array_index == 2:
                    rot_curves["y"] = c
                elif c.array_index == 3:
                    rot_curves["z"] = c
            elif "pat1" in c.data_path:
                if pat1_len == 0:
                    pat1_len = len(c.keyframe_points)
                elif pat1_len != len(c.keyframe_points):
                    raise GMTError(
                        f"FCurve {c.data_path} has channels with unmatching keyframes")

                if c.data_path[c.data_path.rindex(".") + 1:] == "pat1_left_hand":
                    pat1_curves["left_" + str(c.array_index)] = c
                elif c.data_path[c.data_path.rindex(".") + 1:] == "pat1_right_hand":
                    pat1_curves["right_" + str(c.array_index)] = c

        if len(loc_curves) == 3:
            bone.curves.append(self.make_curve(
                loc_curves,
                axes=["x", "y", "z"],
                curve_format=CurveFormat.POS_VEC3,
                group_name=bone_name))

        if len(rot_curves) == 4:
            format = CurveFormat.ROT_QUAT_SCALED \
                if self.gmt_properties.version > 0x10001 \
                else CurveFormat.ROT_QUAT_HALF_FLOAT
            bone.curves.append(self.make_curve(
                rot_curves,
                axes=["w", "x", "y", "z"],
                curve_format=format,
                group_name=bone_name))

        for pat in [p for p in pat1_curves if "0" in p]:
            format = CurveFormat.PAT1_LEFT_HAND \
                if "left" in pat \
                else CurveFormat.PAT1_RIGHT_HAND
            bone.curves.append(self.make_curve(
                pat1_curves,
                axes=[pat, pat[:-1]+"1"],
                curve_format=format,
                group_name=bone_name))

        return bone

    def make_curve(self, fcurves, axes, curve_format, group_name) -> Curve:
        curve = Curve()
        curve.graph = Graph()

        axes_co = []
        for axis in axes:
            axis_co = [0] * 2 * len(fcurves[axis].keyframe_points)
            fcurves[axis].keyframe_points.foreach_get("co", axis_co)
            axes_co.append(axis_co)

        curve.curve_format = curve_format

        interpolate = True
        if len(axes_co) == 3:
            # Position vector
            curve.values = list(map(
                lambda x, y, z: Vector((-x, z, y)),
                axes_co[0][1:][::2],
                axes_co[1][1:][::2],
                axes_co[2][1:][::2]))
            curve.values = self.translate_loc(group_name, curve)
        elif len(axes_co) == 4:
            # Rotation quaternion
            curve.values = list(map(
                lambda w, x, y, z: [-x, z, y, w],
                axes_co[0][1:][::2],
                axes_co[1][1:][::2],
                axes_co[2][1:][::2],
                axes_co[3][1:][::2]))
        elif len(axes_co) == 2:
            # Pat1
            curve.values = list(map(
                lambda s, e: [int(s), int(e)],
                axes_co[0][1:][::2],
                axes_co[1][1:][::2]))
            interpolate = False

        curve.graph.keyframes = [int(x) for x in axes_co[0][::2]]
        curve.graph.delimiter = -1

        if interpolate:
            # Apply constant interpolation by duplicating keyframes
            pol = [True] * len(fcurves[axes[0]].keyframe_points)
            axis_pol = pol.copy()
            for axis in axes:
                fcurves[axis].keyframe_points.foreach_get(
                    "interpolation", axis_pol)
                pol = list(map(lambda a, b: a and (b == 0),
                               pol, axis_pol))  # 'CONSTANT' = 0

            j = 0
            for i in range(len(pol) - 1):
                k = i + j
                if pol[i] and curve.graph.keyframes[k + 1] - curve.graph.keyframes[k] > 1:
                    curve.values.insert(k + 1, curve.values[k])
                    curve.graph.keyframes.insert(
                        k + 1, curve.graph.keyframes[k + 1] - 1)
                    j += 1

        return curve

    def setup_bone_locs(self):
        armature = bpy.data.armatures.get(self.skeleton_name)

        self.heads = {}
        self.parents = {}
        #local_rots = {}

        mode = bpy.context.mode
        bpy.ops.object.mode_set(mode='EDIT')
        for b in armature.edit_bones:
            h = b["head_no_rot"].to_list() if "head_no_rot" in b else b.head
            self.heads[b.name] = Vector((-h[0], h[2], h[1]))
            if b.parent:
                self.parents[b.name] = b.parent.name
            """
            if "local_rot" in b:
                if b.name == 'oya2_r_n' or b.name == 'oya3_r_n':
                    local_rots[b.name] = local_rots['oya1_r_n'].inverted()
                if b.name == 'oya2_l_n' or b.name == 'oya3_l_n':
                    local_rots[b.name] = local_rots['oya1_l_n'].inverted()
                local_rots[b.name] = Quaternion(b["local_rot"].to_list())
            else:
                local_rots[b.name] = Quaternion()
            """
        bpy.ops.object.mode_set(mode=mode)

    def translate_loc(self, name, curve):
        if name in self.parents:
            curve.values = [(x + self.heads[name]) -
                            self.heads[self.parents[name]] for x in curve.values]
        else:
            curve.values = [(x + self.heads[name]) for x in curve.values]

        return curve.values


def menu_func_export(self, context):
    self.layout.operator(ExportGMT.bl_idname, text='Yakuza Animation (.gmt)')
