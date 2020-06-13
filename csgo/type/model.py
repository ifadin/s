from enum import Enum


class Model(Enum):
    BCK = 'BCK'
    BS = 'BS'
    DM = 'DM'
    HX = 'HX'
    LF = 'LF'

    @staticmethod
    def from_str(value: str):
        names = {
            'bck': Model.BCK,
            'bs': Model.BS,
            'dm': Model.DM,
            'hx': Model.HX,
            'lf': Model.LF
        }

        return names.get(value.lower())