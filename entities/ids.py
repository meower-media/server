import time, os
from threading import Lock


"""
ID Format:
Timestamp (42-bits)
Node ID (11-bits)
Increment (11-bits)
"""


MEOWER_EPOCH = 1420070400000

TIMESTAMP_BITS = 41
NODE_ID_BITS = 11
INCREMENT_BITS = 11

NODE_ID = int(os.environ["NODE_ID"])

lock = Lock()
last_timestamp = 0
increment = 0


def gen_id():
    # Get global variables and acquire lock
    global increment, last_timestamp
    lock.acquire()

    # Get increment
    if time.time() != last_timestamp:
        last_timestamp = time.time()
        increment = 0
    elif increment >= (2 ** INCREMENT_BITS)-1:
        while time.time() == last_timestamp:
            time.sleep(0)
        last_timestamp = time.time()
        increment = 0
    else:
        increment += 1

    # Get timestamp
    timestamp = int((time.time() * 1000) - MEOWER_EPOCH)

    # Construct ID
    id = timestamp << (NODE_ID_BITS + INCREMENT_BITS) | NODE_ID << INCREMENT_BITS | increment

    # Release lock
    lock.release()

    # Return ID
    return id

def extract_timestamp(id: int) -> int:
    return id >> 22 + MEOWER_EPOCH
