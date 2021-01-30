import bpy
from yakuza_gmt.blender.error import GMTError


class AddHandPattern(bpy.types.Operator):
    bl_idname = "action.add_hand_pattern"
    bl_label = "Add Hand Pattern"

    def execute(self, context):
        if bpy.context.mode != 'POSE':
            raise GMTError("Current mode is not Pose mode")
        bone = [b for b in bpy.context.active_object.pose.bones if "pattern" in b.name]
        if not len(bone):
            raise GMTError("Pattern bone not found")
        bone_name = bone[0].name

        action = bpy.context.active_object.animation_data.action

        group = [g for g in action.groups if g.name == bone_name]
        if len(group):
            group = group[0]
        else:
            group = action.groups.new(bone_name)

        left_hand = []
        right_hand = []

        for c in group.channels:
            if "pat1_left_hand" in c.data_path:
                left_hand.append(c)
            elif "pat1_right_hand" in c.data_path:
                right_hand.append(c)

        if not len(left_hand):
            for i in range(2):
                left_hand[i] = action.fcurves.new(
                    data_path=f'pose.bones["{group.name}"].pat1_left_hand', index=i, action_group=group.name)

        if not len(right_hand):
            for i in range(2):
                right_hand[i] = action.fcurves.new(
                    data_path=f'pose.bones["{group.name}"].pat1_right_hand', index=i, action_group=group.name)

        # Now that you have the necessary curves, open a menu/panel or something where you can add individual entries with a button
        # Each entry will have: hand (left or right), start pattern, interpolation pattern, start frame, end frame
        # After clicking Apply, the entries will be used to generate the curves for the patterns. these will replace the original curves

        return {'FINISHED'}


class GMTTools(bpy.types.Menu):
    bl_idname = "scene.gmt_tools"
    bl_label = "GMT Tools"
    bl_space_type = 'DOPESHEET_EDITOR'

    def draw(self, context):
        layout = self.layout

        layout.operator("action.add_hand_pattern")

    def execute(self, context):
        return {'FINISHED'}


def menu_func_tools(self, context):
    self.layout.separator()
    self.layout.menu(GMTTools.bl_idname, text='GMT Tools')
