class Name:
    def __init__(self, string: str):
        self.__string = string
        self.__checksum = sum(string.encode('shift-jis'))

    __checksum: int
    __string: str

    def update(self, new_string: str):
        self.__string = new_string
        self.__checksum = sum(new_string.encode('shift-jis'))

    def checksum(self):
        return self.__checksum

    def string(self):
        return self.__string
