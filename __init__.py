import importlib.util

blender_loader = importlib.util.find_spec('bpy')

# Include the bl_info at the top level always
bl_info = {
    "name": "Yakuza GMT File Import/Export",
    "author": "SutandoTsukai181",
    "version": (0, 9, 0),
    "blender": (2, 93, 0),
    "location": "File > Import-Export",
    "description": "Import-Export Yakuza GMT Files",
    "warning": "",
    "doc_url": "https://github.com/SutandoTsukai181/yakuza-gmt-blender/wiki",
    "tracker_url": "https://github.com/SutandoTsukai181/yakuza-gmt-blender/issues",
    "category": "Import-Export",
}

if blender_loader:
    from .blender.addon import *
