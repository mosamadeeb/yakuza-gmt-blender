from os.path import basename
from typing import List

from .util.binary import BinaryReader


class CMTData:
    def __init__(self):
        pass
    pos_x: float
    pos_y: float
    pos_z: float
    fov: float
    foc_x: float
    foc_y: float
    foc_z: float
    rot: float


class CMTAnimation:
    def __init__(self):
        pass
    frame_rate: float
    frame_count: int
    anm_data_offset: int
    format: int

    anm_data: List[CMTData]


class CMTHeader:
    def __init__(self):
        pass
    big_endian: bool
    version: int
    data_size: int

    anm_count: int
    unk1: int
    unk2: int
    unk3: int


class CMTFile:
    def __init__(self):
        pass
    name: str
    header: CMTHeader
    animations: List[CMTAnimation]


def read_header(cmt: BinaryReader) -> CMTHeader:
    header = CMTHeader()

    cmt.skip(1)
    header.big_endian = bool(cmt.read_uint8())
    cmt.set_endian(header.big_endian)
    cmt.skip(2)
    header.version = cmt.read_uint32()
    header.data_size = cmt.read_uint32()

    header.anm_count = cmt.read_uint32()
    header.unk1 = cmt.read_uint32()
    header.unk2 = cmt.read_uint32()
    header.unk3 = cmt.read_uint32()

    return header


def read_animations(cmt: BinaryReader, header: CMTHeader) -> List[CMTAnimation]:
    anm_list = []
    for i in range(header.anm_count):
        anm = CMTAnimation()

        cmt.seek((i * 0x10) + 0x20)

        anm.frame_rate = cmt.read_float()
        anm.frame_count = cmt.read_uint32()
        anm.anm_data_offset = cmt.read_uint32()
        anm.format = cmt.read_uint32()

        cmt.seek(anm.anm_data_offset)
        anm.anm_data = read_animation_data(cmt, anm.frame_count, anm.format)

        anm_list.append(anm)

    return anm_list


def read_animation_data(cmt: BinaryReader, count: int, format: int) -> List[CMTData]:
    anm_data_list = []

    # formats 4, 2, and 0 are similar
    # format 1 may have 16bit values
    if format & 0x10000:
        raise("Unexpected format")

    for i in range(count):
        data = CMTData()

        data.pos_x = cmt.read_float()
        data.pos_y = cmt.read_float()
        data.pos_z = cmt.read_float()
        data.fov = cmt.read_float()

        data.foc_x = cmt.read_float()
        data.foc_y = cmt.read_float()
        data.foc_z = cmt.read_float()
        data.rot = cmt.read_float()

        anm_data_list.append(data)

    return anm_data_list


def read_cmt_file(path: str) -> CMTFile:
    file = CMTFile()

    f = open(path, "rb")
    cmt = BinaryReader(f.read())
    f.close()

    if cmt.read_str(4) != "CMTP":
        print("Invalid magic")
        return "Invalid magic"

    file.name = basename(path)[:-4]

    file.header = read_header(cmt)

    if file.header.version not in [0x40000, 0x20000, 0x10001]:
        print("Unsupported version: " + str(file.header.version))
        return ("Unsupported version: " + str(file.header.version))

    file.animations = read_animations(cmt, file.header)

    return file
