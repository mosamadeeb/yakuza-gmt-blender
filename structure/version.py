from enum import Enum, auto

# Used for translating arguments to game names
GAME = {
    'y0': 'YAKUZA_0',
    'yk1': 'YAKUZA_K',
    'yk2': 'YAKUZA_K2',
    'y3': 'YAKUZA_3',
    'y4': 'YAKUZA_4',
    'y5': 'YAKUZA_5',
    'y6': 'YAKUZA_6',
    'yken': 'KENZAN',
    'yish': 'ISHIN',
    'yds': 'DEAD_SOULS',
    'fotns': 'FOTNS',
    'je': 'JUDGMENT'
}

# [version, new_bones, is_dragon_engine]
GMT_VERSION = {
    'KENZAN':     [0x10001, False, False],
    'YAKUZA_3':   [0X20000, False, False],
    'YAKUZA_4':   [0X20000, False, False],
    'DEAD_SOULS': [0X20000, False, False],
    'YAKUZA_5':   [0X20001, False, False],
    'ISHIN':      [0X20002, True, False],
    'YAKUZA_0':   [0X20002, True, False],
    'YAKUZA_K':   [0X20002, True, False],
    'YAKUZA_6':   [0X20002, True, True],
    'YAKUZA_K2':  [0X20002, True, True],
    'FOTNS':      [0X20002, True, False],
    'JUDGMENT':   [0X20002, True, True],
    'YAKUZA_7':   [0X20002, True, True]
}


class Context(Enum):
    HACT = auto(),
    MOTION = auto()


# Version: GMT version in the header
#   0x10001: uses half floats for rotation formats 0x2, 0x13, 0x14, 0x15
#   0x20000: moved over to scaled floats (signed short int) for the above formats
#   0x20001: introduced format 0x1E for rotation
#   0x20002: allowed usage of vector_c_n for both engines and sync_c_n (DE only) for
#            full model translations
#
# New Bones: animations have vector_c_n to use for translations instead of center bone
#
# Dragon Engine: the new engine introduced in Y6
#   all skeletons used in dragon engine have the top bone (ketu) as a parent to the
#   bottom bone (kosi), where in the old engine both bones were siblings, and direct children
#   to the center bone
#
# Context: the origin of the GMT animation
#   old engine games that use vector bone (Ishin/Y0/K1/FOTNS) behave differently according to
#   whether the gmt is located in motion (for everything that is not a cutscene) or hact/auth
#
#   motion gmts rely on center bone for vertical movement, and on vector for horizontal plane movement
#   hact and auth gmts need both center and vector to have full movement (or maybe only center?)
#   it is currently unknown whether rotations are used in the same manner or not
#
class GMTProperties:
    def __init__(self, game: str):
        props = GMT_VERSION[game]
        self.version: int = props[0]
        self.new_bones: bool = props[1]
        self.is_dragon_engine: bool = props[2]

    context: Context

    def set_context(self, context: int):
        if context == 0:
            self.context = Context.HACT
        elif context == 1:
            self.context = Context.MOTION
