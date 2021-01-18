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


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
    # for f in extension_panel_unregister_functors:
    #    f()
    # extension_panel_unregister_functors.clear()

    # remove from the export / import menu
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
