import struct
from itertools import chain

FMT = {}
for c in ["i", "I", "f"]:
    FMT[c] = 4
for c in ["h", "H", "e"]:
    FMT[c] = 2
for c in ["b", "B", "s"]:
    FMT[c] = 1


class BinaryReader:
    __buf: bytearray
    __idx: int
    __big_end: bool

    def __init__(self, buffer: bytearray):
        self.__buf = buffer
        self.__idx = 0
        self.__big_end = True

    def pos(self):
        return self.__idx

    def size(self):
        return len(self.__buf)

    def buffer(self):
        return self.__buf

    def align(self, size):
        if self.__idx % size:
            pad = size - (self.__idx % size)
            self.__buf.extend([0 for x in range(pad)])
            return pad
        return 0

    def extend(self, buffer: bytearray):
        self.__buf.extend(buffer)

    def seek(self, index: int, from_end=False):
        if index > len(self.__buf) + 1:
            raise(f"BinaryReader Error: cannot seek farther than buffer length!")
        if from_end:
            self.__idx = len(self.__buf) - index
        else:
            self.__idx = index

    def skip(self, length: int):
        if self.__idx + length > len(self.__buf) + 1:
            raise(f"BinaryReader Error: cannot skip farther than buffer length!")
        self.__idx += length

    def set_endian(self, is_big_endian: bool):
        self.__big_end = is_big_endian

    def __read_type(self, format: str, count: int):
        i = self.__idx
        self.__idx += FMT[format] * count

        end = ">" if self.__big_end else "<"

        return struct.unpack_from(end + str(count) + format, self.__buf, i)

    def read_str(self, length=1):
        return self.__read_type("s", length)[0].split(b'\x00', 1)[0].decode('shift-jis')

    def read_int32(self, count=1):
        if count > 1:
            return self.__read_type("i", count)
        return self.__read_type("i", count)[0]

    def read_uint32(self, count=1):
        if count > 1:
            return self.__read_type("I", count)
        return self.__read_type("I", count)[0]

    def read_int16(self, count=1):
        if count > 1:
            return self.__read_type("h", count)
        return self.__read_type("h", count)[0]

    def read_uint16(self, count=1):
        if count > 1:
            return self.__read_type("H", count)
        return self.__read_type("H", count)[0]

    def read_int8(self, count=1):
        if count > 1:
            return self.__read_type("b", count)
        return self.__read_type("b", count)[0]

    def read_uint8(self, count=1):
        if count > 1:
            return self.__read_type("B", count)
        return self.__read_type("B", count)[0]

    def read_float(self, count=1):
        if count > 1:
            return self.__read_type("f", count)
        return self.__read_type("f", count)[0]

    def read_half_float(self, count=1):
        if count > 1:
            return self.__read_type("e", count)
        return self.__read_type("e", count)[0]

    def __write_type(self, format: str, value, count, is_iterable):
        i = self.__idx

        end = ">" if self.__big_end else "<"

        if is_iterable:
            if count == -1:
                count = 1
            count *= len(value)
            if i + (FMT[format] * count) > self.size():
                self.__buf.extend([0 for x in range(FMT[format] * count)])
            struct.pack_into(end + str(count) + format,
                             self.__buf, i, *list(chain(*value)))
        elif count == -1 or type(value) is bytes:
            if count == -1:
                count = 1
            if i + (FMT[format] * count) > self.size():
                self.__buf.extend([0 for x in range(FMT[format] * count)])
            struct.pack_into(end + str(count) + format, self.__buf, i, value)
        else:
            if count == -1:
                count = 1
            if i + (FMT[format] * count) > self.size():
                self.__buf.extend([0 for x in range(FMT[format] * count)])
            struct.pack_into(end + str(count) + format, self.__buf, i, *value)

        self.__idx += FMT[format] * count

        return self.__idx - i

    def write_str(self, string: str, length=1):
        return self.__write_type("s", string.encode('shift-jis'), length, is_iterable=False)

    def write_int32(self, value, count=-1, is_iterable=False):
        return self.__write_type("i", value, count, is_iterable)

    def write_uint32(self, value, count=-1, is_iterable=False):
        return self.__write_type("I", value, count, is_iterable)

    def write_int16(self, value, count=-1, is_iterable=False):
        return self.__write_type("h", value, count, is_iterable)

    def write_uint16(self, value, count=-1, is_iterable=False):
        return self.__write_type("H", value, count, is_iterable)

    def write_int8(self, value, count=-1, is_iterable=False):
        return self.__write_type("b", value, count, is_iterable)

    def write_uint8(self, value, count=-1, is_iterable=False):
        return self.__write_type("B", value, count, is_iterable)

    def write_float(self, value, count=-1, is_iterable=False):
        return self.__write_type("f", value, count, is_iterable)

    def write_half_float(self, value, count=-1, is_iterable=False):
        return self.__write_type("e", value, count, is_iterable)
