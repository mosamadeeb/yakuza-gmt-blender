from math import tan
from typing import Dict

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from mathutils import Euler, Matrix, Quaternion, Vector
from yakuza_gmt.blender.coordinate_converter import (pos_to_blender,
                                                     rot_to_blender)
from yakuza_gmt.blender.error import GMTError
from yakuza_gmt.read import read_file
from yakuza_gmt.read_cmt import *
from yakuza_gmt.structure.file import *
from yakuza_gmt.structure.types.format import CurveFormat, get_curve_properties


class ImportGMT(Operator, ImportHelper):
    """Loads a GMT file into blender"""
    bl_idname = "import_scene.gmt"
    bl_label = "Import Yakuza GMT"

    filter_glob: StringProperty(default="*.gmt;*.cmt", options={"HIDDEN"})
    # files: CollectionProperty(
    #    name="File Path",
    #    type=bpy.types.OperatorFileListElement,
    # )
    # Only allow importing one file at a time
    #file: StringProperty(name="File Path", subtype="FILE_PATH")

    #load_materials: BoolProperty(name="Load DE Animation For Old Engine", default=True)
    """
    def item_callback(self, context):
        return (
            ('NO_CHANGE', 'No change', "Import/Export to same type of skeleton"),
            ('FIX_FROM_DE', 'From Dragon Engine', "Dragon Engine animation to old engine skeleton"),
            ('FIX_FROM_OLD', 'To Dragon Engine', "Old engine animation to Dragon Engine skeleton"),
        )
    """
    de_bone_fix: EnumProperty(
        items=[('NO_CHANGE', 'None', "Import/Export to same type of skeleton"),
               ('FIX_FROM_OLD', 'From Old Engine',
                "Old engine animation to Dragon Engine skeleton"),
               ('FIX_FROM_DE', 'From Dragon Engine', "Dragon Engine animation to old engine skeleton")],
        name="DE Bone Fix",
        description="Fix Dragon Engine animations' bone rotation when using an old engine skeleton, or vice versa",
        default=None,
        options={'ANIMATABLE'},
        update=None,
        get=None,
        set=None)

    frame_density: EnumProperty(
        items=[('HIGHEST', 'Highest (100%)', "Import all keyframes"),
               ('HIGHER', 'Higher (75%)', "Import 3/4 of the keyframes"),
               ('HIGH', 'High (66%)', "Import 2/3 of the keyframes"),
               ('MEDIUM', 'Medium (50%)', "Import half of the keyframes"),
               ('LOW', 'Low (33%)', "Import 1/3 of the keyframes"),
               ('LOWEST', 'Lowest (25%)', "Import 1/4 of the keyframes")],
        name="Frame Density",
        description="Percentage of frames to import (lower options may increase performance)",
        default=None,
        options={'ANIMATABLE'},
        update=None,
        get=None,
        set=None)

    use_vector: EnumProperty(
        items=[('CENTER', 'Center', "Do not use vector animation (default)"),
               ('VECTOR', 'Vector (DE)', "Use vector animation (for DE)"),
               ('CENTER_VECTOR', 'Center + Vector', "Use vector in center position (for Y0/YK motion)")],
        name="Vector Translation",
        description="Use vector_c_n instead of center_c_n to animate whole object movements (Needed for DE animations)",
        default=None,
        options={'ANIMATABLE'},
        update=None,
        get=None,
        set=None)

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = True  # No animation.

        layout.prop(self, 'de_bone_fix')

        layout.prop(self, 'use_vector')

        #layout.prop(self, 'frame_density')

    def execute(self, context):
        import time

        arm = self.check_armature()
        if arm is str:
            self.report({"ERROR"}, arm)
            return {'CANCELLED'}

        try:
            start_time = time.time()
            if self.filepath.endswith('.cmt'):
                importer = CMTImporter(
                    self.filepath, self.as_keywords(ignore=("filter_glob",)))
                importer.read()
            else:
                importer = GMTImporter(
                    self.filepath, self.as_keywords(ignore=("filter_glob",)))
                importer.read()

            elapsed_s = "{:.2f}s".format(time.time() - start_time)
            print("GMT import finished in " + elapsed_s)

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

        return "No armature found to add animation to"


class CMTImporter:
    def __init__(self, filepath, import_settings: Dict):
        self.filepath = filepath

    cmt_file: CMTFile

    def read(self):
        self.cmt_file = read_cmt_file(self.filepath)
        if type(self.cmt_file) is str:
            raise GMTError(self.cmt_file)

        self.animate_camera()

    def animate_camera(self):
        camera = bpy.context.scene.camera

        if not camera.animation_data:
            camera.animation_data_create()

        camera.rotation_mode = 'QUATERNION'
        camera.data.lens_unit = 'MILLIMETERS'
        camera.data.sensor_fit = 'VERTICAL'
        camera.data.sensor_height = 100.0

        #sensor_diag = sqrt((camera.data.sensor_width ** 2 + camera.data.sensor_height ** 2))

        for anm in self.cmt_file.animations:
            frame_count = anm.frame_count
            camera.animation_data.action = bpy.data.actions.new(
                name=self.cmt_file.name)
            action = camera.animation_data.action

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
                location = action.fcurves.new(data_path=('location'), index=i)
                location.keyframe_points.add(anm.frame_count)
                location.keyframe_points.foreach_set(
                    "co", [x for co in zip(frames, loc) for x in co])
                location.update()
            for i in range(4):
                rot = [x[i] for x in rotations]
                rotation = action.fcurves.new(
                    data_path=('rotation_quaternion'), index=i)
                rotation.keyframe_points.add(anm.frame_count)
                rotation.keyframe_points.foreach_set(
                    "co", [x for co in zip(frames, rot) for x in co])
                rotation.update()

            angle = action.fcurves.new(data_path=('data.lens'))
            angle.keyframe_points.add(anm.frame_count)
            angle.keyframe_points.foreach_set(
                "co", [x for co in zip(frames, foc_lengths) for x in co])
            angle.update()

        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_current = 0
        bpy.context.scene.frame_end = frame_count

    def get_cam_rotations(self, anm: CMTAnimation):
        rotations = []
        for data in anm.anm_data:
            pos = Vector((data.pos_x, data.pos_y, data.pos_z))
            foc = Vector((data.foc_x, data.foc_y, data.foc_z))
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
    def __init__(self, filepath, import_settings: Dict):
        self.filepath = filepath
        self.de_bone_fix = import_settings.get("de_bone_fix")
        self.frame_density = import_settings.get("frame_density")
        self.use_vector = import_settings.get("use_vector")

    gmt_file: GMTFile

    def read(self):
        self.gmt_file = read_file(self.filepath)
        if type(self.gmt_file) is str:
            raise GMTError(self.gmt_file)

        self.make_actions()

    def make_actions(self):
        ao = bpy.context.active_object

        print("Importing file: " + self.gmt_file.header.file_name.string())

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

        bpy.ops.object.mode_set(mode=mode)
        ao.hide_set(hidden)

        frame_count = 1
        frame_rate = 30
        for anm in self.gmt_file.animations:
            frame_count = max(frame_count, anm.frame_count)
            frame_rate = anm.frame_rate

            act_name = f"{anm.name.string()}({self.gmt_file.header.file_name.string()})"

            ao.animation_data.action = bpy.data.actions.new(name=act_name)
            action = ao.animation_data.action

            bones = {}
            for b in anm.bones:
                if b.name.string() in ao.pose.bones:
                    bones[ao.pose.bones[b.name.string()]] = b
                else:
                    print('WARNING: Skipped bone: "%s"' % b.name.string())

            if str(self.de_bone_fix) != "NO_CHANGE":
                ketu = [x for x in bones.items() if "ketu" in x[1].name.string()]
                kosi = [x for x in bones.items() if "kosi" in x[1].name.string()]
                if len(ketu) and len(kosi):
                    bone_pair = (ketu[0][1], kosi[0][1])
                    for c in bone_pair[0].curves:
                        c.data_path = get_curve_properties(c.curve_format)
                    if not len([x for x in bone_pair[1].curves if 'POS' in x.curve_format.name]):
                        bone_pair[1].curves.append(bone_pair[0].curves[0])
                    for c in bone_pair[1].curves:
                        values = []
                        c.data_path = get_curve_properties(c.curve_format)
                        c_ketu = [
                            x for x in bone_pair[0].curves if x.data_path == c.data_path][0]
                        i = 0
                        for k in c.graph.keyframes:
                            kf = k
                            if not k in c_ketu.graph.keyframes:
                                kf = [
                                    x for x in c_ketu.graph.keyframes if x < k][-1]
                            ketu_value = c_ketu.values[c_ketu.graph.keyframes.index(
                                kf)]
                            kosi_value = c.values[i]
                            if c.data_path == "location":
                                ketu_v = Vector(
                                    (-ketu_value[0], ketu_value[2], ketu_value[1]))
                                if str(self.de_bone_fix) == "FIX_FROM_OLD":
                                    new_value = [0, 0, 0, 0]
                                elif str(self.de_bone_fix) == "FIX_FROM_DE":
                                    new_value = [*ketu_v]
                                values.append(
                                    Vector((-new_value[0], new_value[2], new_value[1])))
                            elif c.data_path == "rotation_quaternion":
                                ketu_v = Quaternion(
                                    (ketu_value[3], -ketu_value[0], ketu_value[2], ketu_value[1]))
                                kosi_v = Quaternion(
                                    (kosi_value[3], -kosi_value[0], kosi_value[2], kosi_value[1]))
                                if str(self.de_bone_fix) == "FIX_FROM_OLD":
                                    new_value = [
                                        *ketu_v.inverted().cross(kosi_v)]
                                elif str(self.de_bone_fix) == "FIX_FROM_DE":
                                    new_value = [*ketu_v.cross(kosi_v)]
                                values.append(new_value)
                            i += 1
                        if len(values):
                            c.values = values
                    bones[kosi[0][0]] = bone_pair[1]
            heads = {}
            local_rots = {}
            bpy.ops.object.mode_set(mode='EDIT')
            for b in ao.data.edit_bones:
                if "head_no_rot" in b:
                    heads[b.name] = Vector(b["head_no_rot"].to_list())
                else:
                    heads[b.name] = b.head
                if "local_rot" in b:
                    if b.name == 'oya2_r_n' or b.name == 'oya3_r_n':
                        local_rots[b.name] = local_rots['oya1_r_n'].inverted()
                    if b.name == 'oya2_l_n' or b.name == 'oya3_l_n':
                        local_rots[b.name] = local_rots['oya1_l_n'].inverted()
                    local_rots[b.name] = Quaternion(b["local_rot"].to_list())
                else:
                    local_rots[b.name] = Quaternion()
            bpy.ops.object.mode_set(mode='POSE')

            # Frame density
            """
            if self.frame_density != 'HIGHEST':
                if self.frame_density == 'HIGHER':
                    factor = (4, 0)
                elif self.frame_density == 'HIGH':
                    factor = (3, 0)
                elif self.frame_density == 'MEDIUM':
                    factor = (2, 0)
                elif self.frame_density == 'LOW':
                    factor = (2, 1)
                elif self.frame_density == 'LOWEST':
                    factor = (2, 2)
            """

            # now you should update g.keyframe's and add a new property to Graph
            # then add this to the curve loop:
            # if Graph.indices: update values with indices

            # vector - center.head
            bc = None
            cc = None
            for b in bones.items():
                b = list(b)
                if self.use_vector != 'CENTER':
                    if b[1].name.string() == 'center_c_n':
                        bc = b[0]
                        for c in b[1].curves:
                            if 'POS' in c.curve_format.name:
                                cc = c
                        if not len(b[1].curves):
                            b[1].curves.append(new_pos_curve())
                        continue
                    elif b[1].name.string() == 'vector_c_n':
                        if bc:
                            if not cc:
                                for c in b[1].curves:
                                    if 'POS' in c.curve_format.name:
                                        x, y, z = (0.0, 1.14, 0.0)
                                        if heads['center_c_n']:
                                            x, z, y = heads['center_c_n']
                                            x = -x
                                        c.values = list(
                                            map(lambda p: Vector((p[0] + x, p[1] + y, p[2] + z)), c.values))
                            b[0] = bc
                            b[1].name = Name('center_c_n')
                            if self.use_vector == 'CENTER_VECTOR':
                                if not cc:
                                    continue
                                c.neutralize_pos()
                                cc.curve_format = CurveFormat.POS_Y
                                b[1].curves.insert(0, cc)
                                # for c in b[1].curves:
                                #    if 'POS' in c.curve_format.name and cc:
                                #        c.neutralize_pos()
                                #        c.values = list(map(lambda x: Vec3(x[0], x[1] + cc.values[0][1], x[2]), c.values))
                                """
                                for c in b[1].curves:
                                    if 'POS' in c.curve_format.name:
                                        h = heads['center_c_n']
                                        c.neutralize_pos()
                                        c.values = list(map(lambda x: Vec3(x[0], x[1] + h[2], x[2]), c.values))
                                """
                                """
                                for c in b[1].curves:
                                    if 'POS' in c.curve_format.name and cc:
                                        h = heads['center_c_n']
                                        c.neutralize_pos()
                                        
                                        new_values = []
                                        for f in c.graph.keyframes:
                                            kf = f
                                            if kf not in cc.graph.keyframes:
                                                kf = [k for k in cc.graph.keyframes if k < kf][-1]
                                            new_values.append(cc.values[cc.graph.keyframes.index(kf)])
                                        cc.values = new_values

                                        #if len(c.values) > len(cc.values):
                                        #    cc.values.extend([cc.values[-1]] * (len(c.values) - len(cc.values)))
                                        #cc.values = cc.values[:len(c.values)]
                                        c.values = list(map(lambda x, y: Vec3(x[0], x[1] + y[1], x[2]), c.values, cc.values))
                                """

                group = action.groups.new(b[0].name)
                print("Importing ActionGroup: " + group.name)
                for c in b[1].curves:
                    c.data_path = get_curve_properties(c.curve_format)
                    if c.data_path == "":
                        continue

                    # Frame density
                    """
                    if self.frame_density != 'HIGHEST':
                        i = 0
                        n = 0
                        new_frames, indices, values = [0], [0], []
                        for f in c.graph.keyframes:
                            if i % factor[0]:
                                indices.append(c.graph.keyframes.index(f))
                                new_frames.append(f)
                                i += 1
                                continue
                            if (f - new_frames[-1]) > 4 or c.graph.keyframes.index(f) == len(c.graph.keyframes) - 1:
                                indices.append(c.graph.keyframes.index(f))
                                new_frames.append(f)
                                i += 1
                                continue
                            if n < factor[1]:
                                n += 1
                                continue
                            n = 0
                            i += 1
                        c.graph.keyframes = new_frames
                        c.graph.values_indices = indices
                        print(f"first: {c.values[0]}")
                        for i in indices:
                            values.append(c.values[i])
                        print(f"first2: {c.values[0]}")
                        c.values = values
                    """

                    values = self.convert_values(c, group.name)
                    if c.data_path == "location":
                        if 'center' in b[1].name.string() and self.use_vector == 'CENTER_VECTOR':
                            print(c.curve_format.name)
                            if 'Y' in c.curve_format.name:
                                # print("Y")
                                vs = [(x[2] - heads[b[0].name][2])
                                      for x in values]
                                fcurve = action.fcurves.new(data_path=(
                                    'pose.bones["%s"].' % b[0].name + c.data_path), index=2, action_group=group.name)
                                fcurve.keyframe_points.add(
                                    len(c.graph.keyframes))
                                fcurve.keyframe_points.foreach_set(
                                    "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
                                fcurve.update()
                            elif 'VEC' in c.curve_format.name:
                                for v in [0, 1]:
                                    #print("VEC " + str(v))
                                    vs = [(x[v] - heads[b[0].name][v])
                                          for x in values]
                                    fcurve = action.fcurves.new(data_path=(
                                        'pose.bones["%s"].' % b[0].name + c.data_path), index=v, action_group=group.name)
                                    fcurve.keyframe_points.add(
                                        len(c.graph.keyframes))
                                    fcurve.keyframe_points.foreach_set(
                                        "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
                                    fcurve.update()
                            continue
                        for v in range(len(values[0])):
                            vs = [(x[v] - heads[b[0].name][v]) for x in values]
                            if b[0].parent:
                                vs = [(x[v] - heads[b[0].name][v]) +
                                      heads[b[0].parent.name][v] for x in values]
                            fcurve = action.fcurves.new(data_path=(
                                'pose.bones["%s"].' % b[0].name + c.data_path), index=v, action_group=group.name)
                            fcurve.keyframe_points.add(len(c.graph.keyframes))
                            fcurve.keyframe_points.foreach_set(
                                "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
                            fcurve.update()
                    else:
                        # if 'oya1' in b[0].name:
                        """
                            LOCAL ROT FIX DISABLED
                            #values = list(map(lambda x: rotate_quat(local_rots[b[0].name].inverted(), Quaternion(x)), values))
                        """
                        # if 'oya2' in b[0].name or 'oya3' in b[0].name:
                        #    values = list(map(lambda x: local_rots[b[0].name] @ Quaternion(x), values))

                        #values = list(map(lambda x: rotate_quat(Quaternion(x), local_rots[b[0].name]), values))

                        for v in range(len(values[0])):
                            vs = [x[v] for x in values]
                            fcurve = action.fcurves.new(data_path=(
                                'pose.bones["%s"].' % b[0].name + c.data_path), index=v, action_group=group.name)
                            fcurve.keyframe_points.add(len(c.graph.keyframes))
                            fcurve.keyframe_points.foreach_set(
                                "co", [x for co in zip(c.graph.keyframes, vs) for x in co])
                            fcurve.update()

        bpy.context.scene.render.fps = frame_rate
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_current = 0
        bpy.context.scene.frame_end = frame_count

    def convert_values(self, curve: Curve, bone_name: str):
        if curve.data_path == "rotation_quaternion":
            curve.neutralize_rot()
            return [rot_to_blender(v) for v in curve.values]
        elif curve.data_path == "location":
            curve.neutralize_pos()
            return [pos_to_blender(v) for v in curve.values]


def menu_func_import(self, context):
    self.layout.operator(ImportGMT.bl_idname,
                         text='Yakuza Animation (.gmt/.cmt)')


def rotate_quat(quat1: Quaternion, quat2: Quaternion) -> Quaternion:
    quat1.rotate(quat2)
    return quat1
    # return quat2.inverted().rotate(quat1)
