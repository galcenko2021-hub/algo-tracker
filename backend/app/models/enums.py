import enum


class Platform(enum.StrEnum):
    codeforces = "codeforces"
    leetcode = "leetcode"
    yandex = "yandex"
    other = "other"


class SolveSource(enum.StrEnum):
    manual = "manual"
    codeforces = "codeforces"
