def create(flags: list) -> int:
    bitfield = 0
    for flag in flags:
        bitfield |= (1 << flag)
    return bitfield

def has(bitfield: int, flag: int) -> bool:
    return ((bitfield & (1 << flag)) == (1 << flag))

def add(bitfield: int, flag: int) -> int:
    if not has(bitfield, flag):
        bitfield |= (1 << flag)
    return bitfield

def remove(bitfield: int, flag: int) -> str:
    if has(bitfield, flag):
        bitfield ^= (1 << flag)
    return bitfield
