import bpy
from bpy.props import PointerProperty
from yakuza_gmt.blender.exporter import ExportGMT, menu_func_export
from yakuza_gmt.blender.importer import ImportGMT, menu_func_import

classes = (
    ImportGMT,
    ExportGMT,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    # add to the export / import menu
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # add new pattern attributes
    desc = """Sets interpolation states for hand pattern animations.
[0] is the starting state, and [1] is the state to be interpolated over until the next keyframe"""
    bpy.types.PoseBone.pat1_left_hand = bpy.props.IntVectorProperty(
        name="Left Hand", size=2, min=-1, max=25, description=desc, default=(-1, -1))
    bpy.types.PoseBone.pat1_right_hand = bpy.props.IntVectorProperty(
        name="Right Hand", size=2, min=-1, max=25, description=desc, default=(-1, -1))


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
    # for f in extension_panel_unregister_functors:
    #    f()
    # extension_panel_unregister_functors.clear()

    # remove from the export / import menu
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    del bpy.types.PoseBone.pat1_left_hand
    del bpy.types.PoseBone.pat1_right_hand
