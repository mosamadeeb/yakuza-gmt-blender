import struct
from copy import deepcopy
from math import sqrt
from os.path import realpath
from typing import Any, List

from yakuza_gmt.structure.animation import Animation
from yakuza_gmt.structure.bone import Bone
from yakuza_gmt.structure.curve import Curve
from yakuza_gmt.structure.file import GMTFile
from yakuza_gmt.structure.graph import Graph
from yakuza_gmt.structure.header import GMTHeader
from yakuza_gmt.structure.name import Name
from yakuza_gmt.structure.types.format import CurveFormat, parse_format
from yakuza_gmt.util.binary import BinaryReader


def read_header(gmt: BinaryReader) -> GMTHeader:
    header = GMTHeader()

    gmt.skip(1)
    header.big_endian = bool(gmt.read_uint8())
    gmt.set_endian(header.big_endian)
    gmt.skip(2)
    header.version = gmt.read_uint32()
    header.data_size = gmt.read_uint32()
    gmt.skip(2)
    header.file_name = Name(str(gmt.read_str(30)))

    header.anm_count = gmt.read_uint32()
    header.anm_offset = gmt.read_uint32()

    header.graph_count = gmt.read_uint32()
    header.graph_offset = gmt.read_uint32()

    header.graph_data_size = gmt.read_uint32()
    header.graph_data_offset = gmt.read_uint32()

    header.name_count = gmt.read_uint32()
    header.name_offset = gmt.read_uint32()

    header.anm_map_count = gmt.read_uint32()
    header.anm_map_offset = gmt.read_uint32()

    header.bone_map_count = gmt.read_uint32()
    header.bone_map_offset = gmt.read_uint32()

    header.curve_count = gmt.read_uint32()
    header.curve_offset = gmt.read_uint32()

    header.anm_data_size = gmt.read_uint32()
    header.anm_data_offset = gmt.read_uint32()

    gmt.skip(12)
    header.flags = gmt.read_uint32()
    return header


def read_names(gmt: BinaryReader, header: GMTHeader) -> List[str]:
    name_list = []
    for i in range(header.name_count):
        gmt.seek(header.name_offset + (i * 32))

        gmt.skip(2)

        name_list.append(Name(str(gmt.read_str(30))))

    return name_list


def read_graphs(gmt: BinaryReader, header: GMTHeader) -> List[Graph]:
    graph_list = []
    for i in range(header.graph_count):
        graph = Graph()

        gmt.seek(header.graph_offset + (i * 4))

        gmt.seek(gmt.read_uint32())
        for k in range(gmt.read_uint16()):
            graph.keyframes.append(gmt.read_uint16())

        graph.delimiter = gmt.read_int16()

        graph_list.append(graph)

    return graph_list


def read_animation_data(gmt: BinaryReader, format: CurveFormat, count: int) -> List[Any]:
    value_list = []

    if format == CurveFormat.POS_VEC3:
        for k in range(count):
            value_list.append([*gmt.read_float(3)])
    elif format in [CurveFormat.POS_X, CurveFormat.POS_Y, CurveFormat.POS_Z]:
        for k in range(count):
            value_list.append([gmt.read_float()])

    elif format == CurveFormat.ROT_QUAT_SCALED:
        for k in range(count):
            value_list.append([(x / 16_384) for x in gmt.read_int16(4)])
    elif 'W_SCALED' in format.name:
        for k in range(count):
            value_list.append([(x / 16_384) for x in gmt.read_int16(2)])

    elif format == CurveFormat.ROT_QUAT_XYZ_FLOAT:
        for k in range(count):
            xyz = gmt.read_float(3)
            x = (xyz[0] ** 2)
            y = (xyz[1] ** 2)
            z = (xyz[2] ** 2)
            w = 1.0 - (x + y + z)
            w = sqrt(w) if w > 0 else 0
            value_list.append([*xyz, w])
    elif 'W_FLOAT' in format.name:
        for k in range(count):
            value_list.append([*gmt.read_float(2)])

    elif format == CurveFormat.ROT_QUAT_HALF_FLOAT:
        for k in range(count):
            value_list.append([*gmt.read_half_float(4)])
    elif 'W_HALF_FLOAT' in format.name:
        for k in range(count):
            value_list.append([*gmt.read_half_float(2)])

    elif format == CurveFormat.ROT_QUAT_INT_SCALED:
        base_quaternion = [(x / 32_768) for x in gmt.read_int16(4)]
        scale_quaternion = [(x / 32_768) for x in gmt.read_uint16(4)]
        for k in range(count):
            f = gmt.read_uint32()
            axis_order = f & 3
            f = f >> 2

            a1 = 0x3FF00000
            a2 = 0x000FFC00
            a3 = 0x000003FF

            m1 = struct.unpack(">f", b'\x30\x80\x00\x00')[0]
            m2 = struct.unpack(">f", b'\x35\x80\x00\x00')[0]
            m3 = struct.unpack(">f", b'\x3A\x80\x00\x00')[0]

            if not axis_order:
                # x
                y = float(f & a1) * m1
                z = float(f & a2) * m2
                w = float(f & a3) * m3

                y = (y * scale_quaternion[1]) + base_quaternion[1]
                z = (z * scale_quaternion[2]) + base_quaternion[2]
                w = (w * scale_quaternion[3]) + base_quaternion[3]

                x = 1.0 - ((y ** 2) + (z ** 2) + (w ** 2))
                x = sqrt(x) if x > 0 else 0

            elif axis_order == 1:
                x = float(f & a1) * m1
                # y
                z = float(f & a2) * m2
                w = float(f & a3) * m3

                x = (x * scale_quaternion[0]) + base_quaternion[0]
                z = (z * scale_quaternion[2]) + base_quaternion[2]
                w = (w * scale_quaternion[3]) + base_quaternion[3]

                y = 1.0 - ((x ** 2) + (z ** 2) + (w ** 2))
                y = sqrt(y) if y > 0 else 0

            elif axis_order == 2:
                x = float(f & a1) * m1
                y = float(f & a2) * m2
                # z
                w = float(f & a3) * m3

                x = (x * scale_quaternion[0]) + base_quaternion[0]
                y = (y * scale_quaternion[1]) + base_quaternion[1]
                w = (w * scale_quaternion[3]) + base_quaternion[3]

                z = 1.0 - ((x ** 2) + (y ** 2) + (w ** 2))
                z = sqrt(z) if z > 0 else 0

            elif axis_order == 3:
                x = float(f & a1) * m1
                y = float(f & a2) * m2
                z = float(f & a3) * m3
                # w

                x = (x * scale_quaternion[0]) + base_quaternion[0]
                y = (y * scale_quaternion[1]) + base_quaternion[1]
                z = (z * scale_quaternion[2]) + base_quaternion[2]

                w = 1.0 - ((x ** 2) + (y ** 2) + (z ** 2))
                w = sqrt(w) if w > 0 else 0

            value_list.append([x, y, z, w])

    elif 'PAT1' in format.name:
        for k in range(count):
            value_list.append([*gmt.read_int16(2)])

    elif 'PAT2' in format.name:
        for k in range(count):
            value_list.append([gmt.read_int8(1)])

    # TODO: anything else should still be patterns (?)
    else:
        for k in range(count):
            value_list.append([gmt.read_int8(1)])

    return value_list


def read_curves(gmt: BinaryReader, file: GMTFile) -> List[Curve]:
    curve_list = []
    for i in range(file.header.curve_count):
        curve = Curve()

        gmt.seek(file.header.curve_offset + (i * 16))

        curve.graph = deepcopy(file.graphs[gmt.read_uint32()])
        curve.anm_data_offset = gmt.read_uint32()
        curve.property_fmt = gmt.read_uint32()
        curve.format = gmt.read_uint32()

        gmt.seek(curve.anm_data_offset)

        curve.curve_format = parse_format(
            curve.property_fmt, curve.format, file.header.version)
        curve.values = read_animation_data(
            gmt, curve.curve_format, len(curve.graph.keyframes))

        curve_list.append(curve)

    return curve_list


def read_bones(gmt: BinaryReader, file: GMTFile) -> List[Bone]:
    bone_list = []
    for i in range(file.header.bone_map_count):
        bone = Bone()

        gmt.seek(file.header.bone_map_offset + (i * 4))

        bone.name = file.names[file.header.anm_count + i]

        start = gmt.read_uint16()
        for n in range(gmt.read_uint16()):
            bone.curves.append(file.curves[start + n])

        bone_list.append(bone)

    return bone_list


def read_animations(gmt: BinaryReader, file: GMTFile) -> List[Animation]:
    anm_list = []
    for i in range(file.header.anm_count):
        anm = Animation()

        gmt.seek(file.header.anm_offset + (i * 64))
        gmt.skip(4)

        anm.frame_count = gmt.read_uint32()
        anm.index = gmt.read_uint32()  # name_index?
        anm.frame_rate = gmt.read_float()

        anm.index1 = gmt.read_uint32()
        anm.index2 = gmt.read_uint32()

        anm.bone_map_start = gmt.read_uint32()
        anm.bone_map_count = gmt.read_uint32()

        anm.curve_count = gmt.read_uint32()

        anm.index3 = gmt.read_uint32()  # graph_index?
        anm.graph_count = gmt.read_uint32()

        anm.anm_data_size = gmt.read_uint32()
        anm.anm_data_offset = gmt.read_uint32()

        anm.graph_data_size = gmt.read_uint32()
        anm.graph_data_offset = gmt.read_uint32()

        gmt.skip(4)

        anm.name = file.names[i]

        gmt.seek(file.header.anm_map_offset + (i * 4))

        start = gmt.read_uint16()
        for b in range(gmt.read_uint16()):
            anm.bones.append(file.bones[(start - file.header.anm_count) + b])

        start = anm.index3
        for g in range(anm.graph_count):
            anm.graphs.append(file.graphs[start + g])

        start = file.curves.index(
            [b.curves for b in anm.bones if len(b.curves)][0][0])
        for c in range(anm.curve_count):
            anm.curves.append(file.curves[start + c])

        anm_list.append(anm)

    return anm_list


def read_file(path: str) -> GMTFile:
    file = GMTFile()

    f = open(realpath(path), "rb")
    gmt = BinaryReader(f.read())
    f.close()

    if gmt.read_str(4) != "GSGT":
        print("Invalid magic!")
        return

    file.header = read_header(gmt)

    if file.header.version not in [0x20002, 0x20001, 0x20000, 0x10001]:
        print("Unsupported version: " + str(file.header.version))
        return

    file.names = read_names(gmt, file.header)

    file.graphs = read_graphs(gmt, file.header)

    file.curves = read_curves(gmt, file)

    file.bones = read_bones(gmt, file)

    file.animations = read_animations(gmt, file)

    return file
