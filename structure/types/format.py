from enum import Enum
from typing import Tuple

from mathutils import Quaternion


class CurveFormat(Enum):
    # format_minor = 0 is ROT
    # format_minor = 1 is POS
    # format_minor > 1 is PAT
    # (property_fmt, format_major, version)
    UNSUPPORTED = (-1, -1, -1)

    ROT_QUAT_XYZ_FLOAT = (1, 0, 1)
    ROT_QUAT_HALF_FLOAT = (2, 0, 1)
    ROT_QUAT_SCALED = (2, 0, 2)

    POS_X = (4, 1, 1)
    POS_Y = (4, 2, 1)
    POS_Z = (4, 4, 1)
    POS_VEC3 = (6, 0, 1)

    ROT_XW_FLOAT = (0x10, 1, 1)
    ROT_YW_FLOAT = (0x11, 2, 1)
    ROT_ZW_FLOAT = (0x12, 3, 1)

    # Same formats, but with the version difference added for convenience
    ROT_XW_FLOAT_2 = (0x10, 1, 2)
    ROT_YW_FLOAT_2 = (0x11, 2, 2)
    ROT_ZW_FLOAT_2 = (0x12, 3, 2)

    ROT_XW_HALF_FLOAT = (0x13, 1, 1)
    ROT_YW_HALF_FLOAT = (0x14, 2, 1)
    ROT_ZW_HALF_FLOAT = (0x15, 3, 1)

    ROT_XW_SCALED = (0x13, 1, 2)
    ROT_YW_SCALED = (0x14, 2, 2)
    ROT_ZW_SCALED = (0x15, 3, 2)

    PAT1_LEFT_HAND = (0x1C, 0, 1)
    PAT1_RIGHT_HAND = (0x1C, 1, 1)
    PAT1_UNK2 = (0x1C, 2, 1)
    PAT1_UNK3 = (0x1C, 3, 1)

    PAT2 = (0x1D, -1, 1)

    ROT_QUAT_INT_SCALED = (0x1E, 0, 2)


def parse_format(property_fmt: int, format: int, version: int) -> CurveFormat:
    format_minor = format & 0xFF
    format_major = format >> 16

    if format_minor == 0:
        # rotation
        if property_fmt == 1:
            return CurveFormat.ROT_QUAT_XYZ_FLOAT
        elif property_fmt == 2:
            return CurveFormat.ROT_QUAT_SCALED if version > 0x10001 else CurveFormat.ROT_QUAT_HALF_FLOAT
        elif property_fmt == 0x10 and format_major == 1:
            return CurveFormat.ROT_XW_FLOAT_2 if version > 0x10001 else CurveFormat.ROT_XW_FLOAT
        elif property_fmt == 0x11 and format_major == 2:
            return CurveFormat.ROT_YW_FLOAT_2 if version > 0x10001 else CurveFormat.ROT_XW_FLOAT
        elif property_fmt == 0x12 and format_major == 3:
            return CurveFormat.ROT_ZW_FLOAT_2 if version > 0x10001 else CurveFormat.ROT_XW_FLOAT
        elif property_fmt == 0x13 and format_major == 1:
            return CurveFormat.ROT_XW_SCALED if version > 0x10001 else CurveFormat.ROT_XW_HALF_FLOAT
        elif property_fmt == 0x14 and format_major == 2:
            return CurveFormat.ROT_YW_SCALED if version > 0x10001 else CurveFormat.ROT_YW_HALF_FLOAT
        elif property_fmt == 0x15 and format_major == 3:
            return CurveFormat.ROT_ZW_SCALED if version > 0x10001 else CurveFormat.ROT_ZW_HALF_FLOAT
        elif property_fmt == 0x1E:
            return CurveFormat.ROT_QUAT_INT_SCALED
        else:
            raise(f"Unexpected format: {property_fmt}, {format}")
    elif format_minor == 1:
        # position
        if property_fmt == 4:
            if format_major == 1:
                return CurveFormat.POS_X
            elif format_major == 2:
                return CurveFormat.POS_Y
            elif format_major == 4:
                return CurveFormat.POS_Z
            else:
                raise(f"Unexpected format: {property_fmt}, {format}")
        elif property_fmt == 6:
            return CurveFormat.POS_VEC3
    elif format_minor == 4:
        # pattern 0x1C format
        if property_fmt == 0x1C:
            if format_major == 0:
                return CurveFormat.PAT1_LEFT_HAND
            elif format_major == 1:
                return CurveFormat.PAT1_RIGHT_HAND
            elif format_major == 2:
                return CurveFormat.PAT1_UNK2
            elif format_major == 3:
                return CurveFormat.PAT1_UNK3
            else:
                return CurveFormat.UNSUPPORTED
    elif format_minor == 5:
        # pattern 0x1D format
        if property_fmt == 0x1D:
            return CurveFormat.PAT2
            """
            if format_major == 0:
                return CurveFormat.PAT2_UNK0
            elif format_major == 1:
                return CurveFormat.PAT2_UNK1
            elif format_major == 2:
                return CurveFormat.PAT2_UNK2
            elif format_major == 3:
                return CurveFormat.PAT2_UNK3
            elif format_major == 4:
                return CurveFormat.PAT2_UNK4
            elif format_major == 5:
                return CurveFormat.PAT2_UNK5
            else:
                return CurveFormat.UNSUPPORTED
            """

    return CurveFormat.UNSUPPORTED


def pack_curve_format(curve_format: CurveFormat) -> Tuple[int, int]:
    if 'ROT' in curve_format.name:
        format_minor = 0
    elif 'POS' in curve_format.name:
        format_minor = 1
    elif 'PAT1' in curve_format.name:
        format_minor = 4
    elif 'PAT2' in curve_format.name:
        format_minor = 5
    format_major = curve_format.value[1] << 16
    return (curve_format.value[0], format_major + format_minor)


def curve_array_to_quat(format: CurveFormat, value) -> Quaternion:
    if 'XW' in format.name:
        return Quaternion((value[1], value[0], 0, 0))
    elif 'YW' in format.name:
        return Quaternion((value[1], 0, value[0], 0))
    elif 'ZW' in format.name:
        return Quaternion((value[1], 0, 0, value[0]))
    else:
        return Quaternion((value[3], value[0], value[1], value[2]))


def get_curve_properties(format: CurveFormat) -> str:
    if 'ROT' in format.name:
        return "rotation_quaternion"
    elif 'POS' in format.name:
        return "location"
    else:
        return ""
