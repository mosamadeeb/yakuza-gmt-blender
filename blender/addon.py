import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty
from bpy.types import AddonPreferences

from .exporter import ExportGMT, menu_func_export
from .importer import ImportGMT, menu_func_import
from .pattern import PatternIndicesPanel, PatternPanel, apply_patterns


class GMTPatternPreferences(AddonPreferences):
    bl_idname = "yakuza_gmt"

    # TODO: Add descriptions for these

    old_par: StringProperty(
        name="Y3, 4, 5 Pattern.par",
        description="""Path to Old Engine Pattern.par. Can be found in <game_directory>/data/motion/ folder.
Yakuza 5 par contains more patterns than Yakuza 3/4 par""",
        subtype='FILE_PATH',
    )

    new_par: StringProperty(
        name="Y0, K1 Pattern.par",
        description="Path to Yakuza 0/Kiwami 1 Pattern.par. Can be found in <game_directory>/data/motion/ folder",
        subtype='FILE_PATH',
    )

    dragon_par: StringProperty(
        name="Y6, 7, K2 motion.par",
        description="""Path to Dragon Engine motion.par. Can be any par archive containing DE patterns.
Yakuza 7 par contains more patterns than Yakuza 6/Kiwami 2/Judgment par""",
        subtype='FILE_PATH',
    )

    old_bone_par: StringProperty(
        name="Y3, 4, 5 bone.par",
        description="Path to Old Engine bone.par. Can be found in <game_directory>/data/chara_common/ folder",
        subtype='FILE_PATH',
    )

    new_bone_par: StringProperty(
        name="Y0, K1 bone.par",
        description="Path to Yakuza 0/Kiwami 1 bone.par. Can be found in <game_directory>/data/chara_common/ folder",
        subtype='FILE_PATH',
    )

    dragon_bone_par: StringProperty(
        name="Y6, 7, K2 chara.par",
        description="Path to Dragon Engine chara.par. Can be any par archive containing DE bone GMDs",
        subtype='FILE_PATH',
    )

    def draw(self, context):
        layout = self.layout
        layout.label(
            text="Choose the path for Pattern.par for each engine version. Required for pattern previewing")
        layout.prop(self, "old_par")
        layout.prop(self, "new_par")
        layout.prop(self, "dragon_par")
        layout.prop(self, "old_bone_par")
        layout.prop(self, "new_bone_par")
        layout.prop(self, "dragon_bone_par")


classes = (
    ImportGMT,
    ExportGMT,
    PatternPanel,
    PatternIndicesPanel,
    GMTPatternPreferences,
)


@persistent
def change_interpolation(scene):
    if bpy.context.active_object.animation_data:
        for f in bpy.context.active_object.animation_data.action.fcurves:
            if "pat1" in f.data_path:
                for k in f.keyframe_points:
                    k.interpolation = 'CONSTANT'


def register():
    for c in classes:
        bpy.utils.register_class(c)

    # add to the export / import menu
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # add new pattern attributes
    desc = """Sets interpolation states for hand pattern animations.
The animation will be interpolated from the current keyframe's state to the next keyframe's state"""

    bpy.types.PoseBone.pat1_left_hand = bpy.props.IntProperty(
        name="Left Hand", min=-1, max=25, description=desc, default=-1)
    bpy.types.PoseBone.pat1_right_hand = bpy.props.IntProperty(
        name="Right Hand", min=-1, max=25, description=desc, default=-1)

    # add another set of location and rotation attributes so we can store FCurves when a driver is active
    desc_gmt = "Stores GMT FCurves when a driver is enabled"
    bpy.types.PoseBone.gmt_location = bpy.props.FloatVectorProperty(
        name="GMT Location", size=3, subtype="XYZ", description=desc_gmt)
    bpy.types.PoseBone.gmt_rotation_quaternion = bpy.props.FloatVectorProperty(
        name="GMT Quaternion Rotation", size=4, subtype="QUATERNION", description=desc_gmt)

    global types
    types = (
        bpy.types.PoseBone.pat1_left_hand,
        bpy.types.PoseBone.pat1_right_hand,
        bpy.types.PoseBone.gmt_location,
        bpy.types.PoseBone.gmt_rotation_quaternion,
    )

    # add a handler to change pattern curves interpolation to constant on each frame update
    bpy.app.handlers.frame_change_pre.append(change_interpolation)
    bpy.app.handlers.frame_change_post.append(apply_patterns)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    for t in types:
        del t

    # remove from the export / import menu
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
