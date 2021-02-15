import bpy
from bpy.app.handlers import persistent
from yakuza_gmt.blender.exporter import ExportGMT, menu_func_export
from yakuza_gmt.blender.importer import ImportGMT, menu_func_import
from yakuza_gmt.blender.pattern import PatternPanel, PatternIndicesPanel

classes = (
    ImportGMT,
    ExportGMT,
    PatternPanel,
    PatternIndicesPanel,
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


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    for t in types:
        del t

    # remove from the export / import menu
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
