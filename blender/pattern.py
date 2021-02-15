import bpy

class PatternBasePanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "bone"
    
    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and context.active_pose_bone and "pattern" in context.active_pose_bone.name

class PatternPanel(PatternBasePanel, bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    
    bl_idname = "POSEBONE_PT_pattern"
    bl_label = "Pattern Properties"
    
    def draw(self, context):
        layout = self.layout
        
        active_pose_bone = context.active_pose_bone
        layout.prop(active_pose_bone, 'pat1_left_hand')
        layout.prop(active_pose_bone, 'pat1_right_hand')

class PatternIndicesPanel(PatternBasePanel, bpy.types.Panel):
    bl_idname = "POSEBONE_PT_pattern_indices"
    bl_parent_id = "POSEBONE_PT_pattern"
    bl_label = "Pattern Indices"
    bl_options = {"DEFAULT_CLOSED"}
    
    def draw(self, context):
        layout = self.layout
        
        box = layout.grid_flow(columns=2)
        for i in range(27):
            if i < 15:
                box.label(text=f"({HAND_PATTERN[i][3]}) {HAND_PATTERN[i][1]}")
            elif i < 19:
                box.label(text=f"({i-1}) {HAND_PATTERN[i][1]} - [DE] {HAND_PATTERN_DE[i][1]}")
            else:
                box.label(text=f"({i-1}) [DE] {HAND_PATTERN_DE[i][1]}")

HAND_PATTERN = [
    ("NONE", "None", "", -1),
    ("NEUTRAL", "Neutral", "", 0),
    ("GU", "Gu", "", 1),
    ("KATANA", "Katana", "", 2),
    ("HAKO", "Hako", "", 3),
    ("TAIKEN", "Taiken", "", 4),
    ("BOU", "Bou", "", 5),
    ("SHOTGUN", "Shotgun", "", 6),
    ("GUN", "Gun", "", 7),
    ("TONFA", "Tonfa", "", 8),
    ("MAX", "Max", "", 9),
    ("MIDDLE", "Middle", "", 10),
    ("MIDDLE2", "Middle 2", "", 11),
    ("MIN", "Min", "", 12),
    ("TABACO", "Tobacco", "", 13),
    ("ARMY", "Gun 2", "", 14),
    ("MAX2", "Max 2", "", 15),
    ("SHP", "Shp", "", 16),
    ("CHOP", "Chop", "", 17)
]

HAND_PATTERN_DE = [
    ("NONE", "None", "", -1),
    ("NEUTRAL", "Neutral", "", 0),
    ("GU", "Gu", "", 1),
    ("KATANA", "Katana", "", 2),
    ("HAKO", "Hako", "", 3),
    ("TAIKEN", "Taiken", "", 4),
    ("BOU", "Bou", "", 5),
    ("SHOTGUN", "Shotgun", "", 6),
    ("GUN", "Gun", "", 7),
    ("TONFA", "Tonfa", "", 8),
    ("MAX", "Max", "", 9),
    ("MIDDLE", "Middle", "", 10),
    ("MIDDLE2", "Middle 2", "", 11),
    ("MIN", "Min", "", 12),
    ("TABACO", "Tobacco", "", 13),
    ("KAN", "Kan", "", 14),
    ("PHONE", "Phone", "", 15),
    ("HANYOU", "Hanyou", "", 16),
    ("HANYOU2", "Hanyou 2", "", 17),
    ("HANYOU3", "Hanyou 3", "", 18),
    ("HANYOU4", "Hanyou 4", "", 19),
    ("C_HANYOU", "Hanyou C", "", 20),
    ("P_PHONE", "Phone 2", "", 21),
    ("STD", "Std", "", 22),
    ("STD2", "Std 2", "", 23),
    ("C_STD", "Std C", "", 24),
    ("CLUTCH", "Clutch", "", 25)
]

FILE_NAME = [
    '0_Neutral',
    '1_Gu',
    '2_Katana',
    '3_Hako',
    '4_taiken',
    '5_bou',
    '6_shotgun',
    '7_gun',
    '8_tonfa',
    '9_hand_max',
    '10_hand_middle',
    '11_hand_middle2',
    '12_hand_min',
    '13_hand_tabaco_F',
    '14_model2army',
    '15_hand_max2',
    '16_F_shp01',
    '17_chop'
]

for i in FILE_NAME:
    i = 'Hand_parts_' + i + '.gmt'

FILE_NAME_DE = [
    '00_neutral',
    '01_gu',
    '02_katana',
    '03_hako',
    '04_taiken',
    '05_bou',
    '06_shotgun',
    '07_gun',
    '08_tonfa',
    '09_hand_max',
    '10_hand_middle',
    '11_hand_middle2',
    '12_hand_min',
    '13_tabaco',
    '14_kan',
    '15_phone',
    '16_h_hanyou',
    '17_h_hanyou2',
    '18_h_hanyou3',
    '19_h_hanyou4',
    '20_c_hanyou',
    '21_p_phone',
    '22_p_std1',
    '23_p_std2',
    '24_c_std',
    '25_clutch'
]

for i in FILE_NAME_DE:
    i = 'm_handptn_anim_' + i + '.gmt'
