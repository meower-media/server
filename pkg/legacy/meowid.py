import os
import asyncio
import time


def limit_to_64_bits(value):
	# Apply a 64-bit mask
	return value & 0xFFFFFFFFFFFFFFFF


NODE_ID = int(os.environ["NODE_ID"])

MEOWER_EPOCH = 1577836800000  # 2020-01-01 12am GMT

TIMESTAMP_BITS = 41
TIMESTAMP_MASK = (1 << TIMESTAMP_BITS) - 1

NODE_ID_BITS = 11
NODE_ID_MASK = (1 << NODE_ID_BITS) - 1

INCREMENT_BITS = 11

# 64 bytes
idIncrementTs: int = 0
idIncrement: int = 0

lock = asyncio.Lock()


def get_ms() -> int:
	return limit_to_64_bits(round(time.time() * 1000))


async def gen_id() -> int:
	global idIncrementTs
	global idIncrement

	ts = get_ms()
	async with lock:
		if idIncrementTs != ts:
			idIncrementTs = ts
			idIncrement = 0
		elif idIncrement < ((2 ** INCREMENT_BITS) - 1):
			while get_ms() == ts:
				continue
			return await gen_id()
		else:
			idIncrement += 1

		id = (ts - MEOWER_EPOCH) << (NODE_ID_BITS + INCREMENT_BITS)
		id |= (NODE_ID & NODE_ID_MASK) << INCREMENT_BITS
		id |= idIncrement & ((1 << INCREMENT_BITS) - 1)
		return id


def gen_id_injected(ts: int) -> int:
	"""ts is in seconds"""
	ts = limit_to_64_bits(round(ts * 1000))
	global idIncrement
	idIncrement += 1
	id = (ts - MEOWER_EPOCH) << (NODE_ID_BITS + INCREMENT_BITS)
	id |= (NODE_ID & NODE_ID_MASK) << INCREMENT_BITS
	id |= idIncrement & ((1 << INCREMENT_BITS) - 1)
	return id


def extract_id(id: int):
	timestamp = ((id >> (64 - TIMESTAMP_BITS - 1)) & TIMESTAMP_MASK) + MEOWER_EPOCH
	node_id = (id >> (64 - TIMESTAMP_BITS - NODE_ID_BITS - 1) & NODE_ID_MASK)
	increment = id & NODE_ID_MASK

	return timestamp, node_id, increment
