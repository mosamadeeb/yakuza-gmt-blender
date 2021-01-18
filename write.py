from typing import List, Tuple

from yakuza_gmt.structure.animation import Animation
from yakuza_gmt.structure.bone import Bone
from yakuza_gmt.structure.curve import Curve
from yakuza_gmt.structure.file import GMTFile
from yakuza_gmt.structure.graph import Graph
from yakuza_gmt.structure.header import GMTHeader
from yakuza_gmt.structure.name import Name
from yakuza_gmt.structure.types.format import CurveFormat, pack_curve_format
from yakuza_gmt.util.binary import BinaryReader


def write_anm_maps(gmt: GMTFile) -> bytearray:
    anm_maps = BinaryReader(bytearray())
    i = len(gmt.animations)
    for a in gmt.animations:
        anm_maps.write_uint16(i)
        anm_maps.write_uint16(len(a.bones))
        i += len(a.bones)
    anm_maps.align(0x20)
    return anm_maps.buffer()


def write_bone_maps(gmt: GMTFile) -> bytearray:
    bone_maps = BinaryReader(bytearray())
    i = 0
    for b in gmt.bones:
        bone_maps.write_uint16(i)
        bone_maps.write_uint16(len(b.curves))
        i += len(b.curves)
    bone_maps.align(0x20)
    return bone_maps.buffer()


def write_names(gmt: GMTFile) -> bytearray:
    names = BinaryReader(bytearray())
    for n in gmt.names:
        names.write_uint16(n.checksum())
        names.write_str(n.string(), 30)
    return names.buffer()


def write_graphs(gmt: GMTFile) -> Tuple[bytearray, List[int], List[int]]:
    graphs = BinaryReader(bytearray())
    offsets = []
    sizes = []
    for g in gmt.graphs:
        offsets.append(graphs.pos())
        size = graphs.write_uint16(len(g.keyframes))
        size += graphs.write_uint16(g.keyframes, len(g.keyframes))
        size += graphs.write_int16(g.delimiter)
        sizes.append(size)
    graphs.align(0x40)
    return graphs.buffer(), offsets, sizes


def write_animation_data(gmt: GMTFile) -> Tuple[bytearray, List[int], List[int]]:
    anm_data = BinaryReader(bytearray())
    offsets = []
    sizes = []
    for c in gmt.curves:
        if c.curve_format in [CurveFormat.ROT_QUAT_XYZ_FLOAT, CurveFormat.ROT_QUAT_INT_SCALED]:
            c.curve_format = CurveFormat.ROT_QUAT_SCALED if gmt.header.version > 0x10001 else CurveFormat.ROT_QUAT_HALF_FLOAT

        offsets.append(anm_data.pos())
        if 'POS' in c.curve_format.name:
            if 'VEC3' in c.curve_format.name:
                sizes.append(anm_data.write_float(
                    c.values, 3, is_iterable=True))
            else:  # 'X', 'Y', 'Z'
                sizes.append(anm_data.write_float(
                    c.values, 1, is_iterable=True))
        elif 'ROT' in c.curve_format.name:
            if 'QUAT' in c.curve_format.name:
                if 'SCALED' in c.curve_format.name:
                    sizes.append(anm_data.write_int16(list(map(
                        lambda x: [int(y * 16_384) for y in x], c.values)), count=4, is_iterable=True))
                else:  # 'HALF_FLOAT'
                    sizes.append(anm_data.write_half_float(
                        c.values, 4, is_iterable=True))
            elif 'W' in c.curve_format.name:
                if 'W_SCALED' in c.curve_format.name:
                    sizes.append(anm_data.write_int16(list(map(
                        lambda x: [int(y * 16_384) for y in x], c.values)), count=2, is_iterable=True))
                elif 'W_FLOAT' in c.curve_format.name:
                    sizes.append(anm_data.write_float(
                        c.values, 2, is_iterable=True))
                else:  # 'W_HALF_FLOAT'
                    sizes.append(anm_data.write_half_float(
                        c.values, 2, is_iterable=True))
        elif 'PAT1' in c.curve_format.name:
            sizes.append(anm_data.write_int16(c.values, 2, is_iterable=True))
        elif 'PAT2' in c.curve_format.name:
            sizes.append(anm_data.write_int8(c.values, 1, is_iterable=True))
        else:
            # only falls for unknown face_c_n patterns
            sizes.append(anm_data.write_int8(c.values, 1, is_iterable=True))

    anm_data.align(0x40)
    return anm_data.buffer(), offsets, sizes


def write_graph_offsets(gmt: GMTFile, g_offsets: List[int]):
    graph_offsets = BinaryReader(bytearray())
    graph_offsets.write_uint32(g_offsets, len(g_offsets))
    graph_offsets.align(0x10)
    return graph_offsets.buffer()


def write_curves(gmt: GMTFile, anm_data_offsets: List[int]):
    curves = BinaryReader(bytearray())
    offsets = iter(anm_data_offsets)
    for c in gmt.curves:
        curves.write_uint32(gmt.graphs.index(
            [g for g in gmt.graphs if g.keyframes == c.graph.keyframes][0]))
        curves.write_uint32(next(offsets))
        format = pack_curve_format(
            c.curve_format) if c.curve_format.value[1] != -1 else (c.property_fmt, c.format)
        curves.write_uint32(format[0])
        curves.write_uint32(format[1])
    return curves.buffer()


def write_animations(gmt: GMTFile, anm_data_sizes, anm_data_offsets, g_sizes, g_offsets):
    anms = BinaryReader(bytearray())
    bone_map_start = 0
    for a in gmt.animations:
        anms.write_uint32(0)
        anms.write_uint32(a.frame_count)
        anms.write_uint32(a.index)
        anms.write_float(a.frame_rate)
        anms.write_uint32(a.index1)
        anms.write_uint32(a.index2)
        anms.write_uint32(bone_map_start)
        bone_map_start += a.bone_map_count
        anms.write_uint32(a.bone_map_count)
        anms.write_uint32(a.curve_count)
        anms.write_uint32(a.index3)
        anms.write_uint32(a.graph_count)

        """
        first_curve = gmt.curves.index(a.curves[0])
        data_size = 0
        for c in range(a.curve_count):
            data_size += anm_data_sizes[first_curve + c]
        anms.write_uint32(data_size)
        anms.write_uint32(anm_data_offsets[first_curve])
        """
        data_size = 0
        for c in range(a.curve_count):
            data_size += anm_data_sizes[c]
        anms.write_uint32(data_size)
        anms.write_uint32(anm_data_offsets[0])

        first_graph = gmt.graphs.index(a.graphs[0])
        graph_size = 0
        for g in range(a.graph_count):
            graph_size += g_sizes[first_graph + g]
        anms.write_uint32(graph_size)
        anms.write_uint32(g_offsets[first_graph])

        anms.write_uint32(0)
    return anms.buffer()


def write_file(gmt: GMTFile, version: int):
    file = BinaryReader(bytearray())
    gmt.update()

    anm_maps = write_anm_maps(gmt)

    bone_maps = write_bone_maps(gmt)

    names = write_names(gmt)

    graphs, g_offsets, g_sizes = write_graphs(gmt)

    anm_data, anm_data_offsets, anm_data_sizes = write_animation_data(gmt)

    header_alloc = 0x80
    anm_alloc = 0x40 * gmt.header.anm_count
    graph_offsets_alloc = 4 * gmt.header.graph_count
    graphs_off = header_alloc + anm_alloc + graph_offsets_alloc

    if graphs_off % 16:
        graphs_off += (16 - (graphs_off % 16))

    g_offsets = list(map(lambda x: x + graphs_off, g_offsets))

    graph_offsets = write_graph_offsets(gmt, g_offsets)

    curves_off = graphs_off + len(graphs) + \
        len(names) + len(anm_maps) + len(bone_maps)

    curves_size = (0x10 * gmt.header.curve_count)

    anm_data_offsets = list(
        map(lambda x: x + curves_off + curves_size, anm_data_offsets))

    curves = write_curves(gmt, anm_data_offsets)

    animations = write_animations(
        gmt, anm_data_sizes, anm_data_offsets, g_sizes, g_offsets)

    # write header
    file.write_str("GSGT", length=4)
    file.write_uint8(2)
    file.write_uint8(1)
    file.write_uint16(0)
    file.write_uint32(version)
    # file_size
    file.write_uint32(0)

    file.write_uint16(gmt.header.file_name.checksum())
    file.write_str(gmt.header.file_name.string(), 30)

    file.write_uint32(gmt.header.anm_count)
    file.write_uint32(header_alloc)

    file.write_uint32(gmt.header.graph_count)
    file.write_uint32(header_alloc + anm_alloc)

    file.write_uint32(len(graphs))
    file.write_uint32(graphs_off)

    file.write_uint32(gmt.header.name_count)
    file.write_uint32(graphs_off + len(graphs))

    file.write_uint32(gmt.header.anm_count)
    file.write_uint32(graphs_off + len(graphs) + len(names))

    file.write_uint32(gmt.header.bone_map_count)
    file.write_uint32(graphs_off + len(graphs) + len(names) + len(anm_maps))

    file.write_uint32(gmt.header.curve_count)
    file.write_uint32(curves_off)

    file.write_uint32(len(anm_data))
    file.write_uint32(curves_off + len(curves))

    file.write_uint32(0)
    file.write_uint32(0)
    file.write_uint32(0)
    file.write_uint32(gmt.header.flags)

    file.extend(animations)
    file.extend(graph_offsets)
    file.extend(graphs)
    file.extend(names)
    file.extend(anm_maps)
    file.extend(bone_maps)
    file.extend(curves)
    file.extend(anm_data)

    file.seek(0, from_end=True)
    file_size = file.pos()
    file.seek(0xC)
    file.write_uint32(file_size)

    file.seek(0, from_end=True)
    file.align(0x100)

    return file.buffer()
