from collections import UserDict


class ReadOnlyDict(UserDict):
    def __init__(self, data):
        self.data = data

    def __setitem__(self, key, value):
        raise TypeError("readonly dict")

    def __delitem__(self, key):
        raise TypeError("readonly dict")
