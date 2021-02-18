
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

FILE_NAME_NEW = [
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

for i in range(len(FILE_NAME_NEW)):
    FILE_NAME_NEW[i] = 'Hand_parts_' + FILE_NAME_NEW[i] + '.gmt'

FILE_NAME_OLD = FILE_NAME_NEW[:14]

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

for i in range(len(FILE_NAME_DE)):
    FILE_NAME_DE[i] = 'm_handptn_anim_' + FILE_NAME_DE[i] + '.gmt'

FILE_NAME_LISTS = [FILE_NAME_OLD, FILE_NAME_NEW, FILE_NAME_DE]

HAND_BONES_OLD = [
    'kou_r',
    'kou_l'
]

for b in ['naka', 'hito', 'koyu', 'kusu', 'oya']:
    for i in range(1, 4):
        for d in ['r', 'l']:
            HAND_BONES_OLD.append(f'{b}{i}_{d}')

HAND_BONES_NEW = list(map(lambda x: x + "_n", HAND_BONES_OLD))

HAND_BONES_DE = HAND_BONES_NEW[2:]

for b in ['naka', 'hito', 'koyu', 'kusu']:
    for d in ['r', 'l']:
        HAND_BONES_DE.append(f'{b}0_{d}_n')

HAND_BONES_LISTS = [HAND_BONES_OLD, HAND_BONES_NEW, HAND_BONES_DE]

VERSION_STR = ["_old", "_new", "_de"]
