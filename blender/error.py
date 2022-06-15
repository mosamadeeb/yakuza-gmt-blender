class GMTError(Exception):
    msg: str

    def __init__(self, msg: str):
        self.msg = f'GMTError: {msg}'
        super().__init__(self.msg)
