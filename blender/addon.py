import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty
from bpy.types import AddonPreferences

from .exporter import ExportGMT, menu_func_export
from .importer import ImportGMT, create_pose_bone_type, menu_func_import
from .pattern import GMTPatternIndicesPanel, GMTPatternPanel, apply_patterns


class GMTPatternPreferences(AddonPreferences):
    bl_idname = "yakuza_gmt"

    use_patterns: BoolProperty(
        name="Use Patterns",
        description="""If disabled, patterns will not be applied to animations, and will not be loaded into
blender with the first GMT import in each session. Reduces load times and improves performance when disabled""",
        default=True)

    old_par: StringProperty(
        name="Y3, 4, 5 Pattern.par",
        description="""Path to Old Engine Pattern.par. Can be found in <game_directory>/data/motion/ folder.
Yakuza 5 par contains more patterns than Yakuza 3/4 par""",
        subtype='FILE_PATH')

    new_par: StringProperty(
        name="Y0, K1 Pattern.par",
        description="Path to Yakuza 0/Kiwami 1 Pattern.par. Can be found in <game_directory>/data/motion/ folder",
        subtype='FILE_PATH')

    dragon_par: StringProperty(
        name="Y6, 7, K2 motion.par",
        description="""Path to Dragon Engine motion.par. Can be any par archive containing DE patterns.
Yakuza 7 par contains more patterns than Yakuza 6/Kiwami 2/Judgment par""",
        subtype='FILE_PATH')

    old_bone_par: StringProperty(
        name="Y3, 4, 5 bone.par",
        description="Path to Old Engine bone.par. Can be found in <game_directory>/data/chara_common/ folder",
        subtype='FILE_PATH')

    new_bone_par: StringProperty(
        name="Y0, K1 bone.par",
        description="Path to Yakuza 0/Kiwami 1 bone.par. Can be found in <game_directory>/data/chara_common/ folder",
        subtype='FILE_PATH')

    dragon_bone_par: StringProperty(
        name="Y6, 7, K2 chara.par",
        description="Path to Dragon Engine chara.par. Can be any par archive containing DE bone GMDs",
        subtype='FILE_PATH')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_patterns")
        layout.label(
            text="Choose the path for Pattern.par and bone.par for each engine version. Required for pattern previewing")
        layout.prop(self, "old_par")
        layout.prop(self, "new_par")
        layout.prop(self, "dragon_par")
        layout.prop(self, "old_bone_par")
        layout.prop(self, "new_bone_par")
        layout.prop(self, "dragon_bone_par")


# Used for storing strings inside a collection property
class StringPropertyGroup(bpy.types.PropertyGroup):
    string: bpy.props.StringProperty()


classes = (
    ImportGMT,
    ExportGMT,
    GMTPatternPanel,
    GMTPatternIndicesPanel,
    StringPropertyGroup,
    # GMTPatternPreferences,
)


@persistent
# Currently unused, since pattern previewing is disabled
def change_interpolation(scene):
    if bpy.context.active_object and bpy.context.active_object.animation_data:
        for f in bpy.context.active_object.animation_data.action.fcurves:
            if 'pat' in f.data_path:
                for k in f.keyframe_points:
                    k.interpolation = 'CONSTANT'


@persistent
def load_pattern_types(dummy):
    if not hasattr(bpy.context.scene, 'pattern_types'):
        print('GMTWarning: Addon did not register correctly - missing collection property in scene')
        return

    global types

    # Load collection from scene
    for pat in getattr(bpy.context.scene, 'pattern_types'):
        types[create_pose_bone_type(bpy.context, pat.string)] = bpy.types.PoseBone


def register():
    for c in classes:
        bpy.utils.register_class(c)

    # Add to the export / import menu
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # Store a collection in the scene to save new pattern types created while importing
    setattr(bpy.types.Scene, 'pattern_types', bpy.props.CollectionProperty(type=StringPropertyGroup))

    pat_desc = """Sets interpolation states for hand pattern animations.
The animation will be interpolated from the current keyframe's state to the next keyframe's state"""

    # Add new pattern attributes
    setattr(bpy.types.PoseBone, 'pat1_left_hand', bpy.props.IntProperty(
        name='Left Hand', min=-1, max=25, description=pat_desc, default=-1))
    setattr(bpy.types.PoseBone, 'pat1_right_hand', bpy.props.IntProperty(
        name='Right Hand', min=-1, max=25, description=pat_desc, default=-1))

    global types
    types = {
        'pattern_types': bpy.types.Scene,
        'pat1_left_hand': bpy.types.PoseBone,
        'pat1_right_hand': bpy.types.PoseBone,
    }

    # Add a handler to change pattern curves interpolation to constant on each frame update
    # bpy.app.handlers.frame_change_pre.append(change_interpolation)
    # bpy.app.handlers.frame_change_post.append(apply_patterns)

    # Add a handler to load pattern types created while importing (from a previous session)
    bpy.app.handlers.load_post.append(load_pattern_types)


def unregister():
    # Remove from the export / import menu
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    # Remove handlers
    bpy.app.handlers.load_post.remove(load_pattern_types)
    # bpy.app.handlers.frame_change_pre.remove(change_interpolation)
    # bpy.app.handlers.frame_change_post.remove(apply_patterns)

    # HACK: Instead of trying to update the types dict from the importer, we just add all the types
    # that were created (from the scene pattern_types collection) to the list in order to delete them
    # Shouldn't cause any issues...
    load_pattern_types(None)

    global types
    for attr in reversed(types):
        delattr(types[attr], attr)

    types.clear()

    for c in reversed(classes):
        bpy.utils.unregister_class(c)
