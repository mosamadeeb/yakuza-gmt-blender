from .name import Name


class GMTHeader:
    def __init__(self):
        pass

    big_endian: bool
    version: int
    data_size: int
    file_name: Name

    anm_count: int
    anm_offset: int
    graph_count: int
    graph_offset: int
    graph_data_size: int
    graph_data_offset: int
    name_count: int
    name_offset: int
    anm_map_count: int
    anm_map_offset: int
    bone_map_count: int
    bone_map_offset: int
    curve_count: int
    curve_offset: int
    anm_data_size: int
    anm_data_offset: int

    flags: int
