#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
https://gist.githubusercontent.com/wakingyeung/c4615dacd5b7789873d9be498af92acc/raw/26f4a5745be117a118942e0fa4eb1390197c8cc9/snowflake.py
"""


import multiprocessing
import re
import threading
import time

LAST_TIMESTAMP = -1
SEQUENCE = 0

WORKER_ID_BITS = 5
DATACENTER_ID_BITS = 5
MAX_WORKER_ID = (1 << WORKER_ID_BITS) - 1
MAX_DATACENTER_ID = (1 << DATACENTER_ID_BITS) - 1
SEQUENCE_BITS = 12

WORKER_ID_SHIFT = SEQUENCE_BITS
DATACENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS
TIMESTAMP_LEFT_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATACENTER_ID_BITS
SEQUENCE_MASK = (1 << SEQUENCE_BITS) - 1

EPOCH = time.mktime((2021, 1, 1, 0, 0, 0, 0, 0, 0))

RE_PATTERN = re.compile(r"\d+")


def has_digit(s: str) -> bool:
    return bool(RE_PATTERN.search(s))


def gen_worker_id(s: str) -> int:
    return int("".join(RE_PATTERN.findall(s)))


def get_timestamp() -> int:
    now = int((time.time()) * 1000)
    return now


def til_next_millis(last: int) -> int:
    timestamp = get_timestamp()
    while timestamp <= last:
        timestamp = get_timestamp()
    return timestamp


def generate_snowflake(worker_id: int = 0, datacenter_id: int = 0, epoch: int = None) -> int:
    global LAST_TIMESTAMP, SEQUENCE

    if not epoch:
        epoch = globals()["EPOCH"]

    proc = multiprocessing.current_process()
    thread = threading.current_thread()
    if worker_id == 0:
        name = ""
        if proc.name != "MainProcess" and has_digit(proc.name):
            name += proc.name
        if thread.name != "MainThread" and has_digit(thread.name):
            name += thread.name
        if name:
            worker_id = gen_worker_id(name)

    worker_id &= MAX_WORKER_ID
    datacenter_id &= MAX_DATACENTER_ID

    timestamp = get_timestamp()
    if timestamp < LAST_TIMESTAMP:
        raise ValueError("Clock moved backwards")

    if timestamp == LAST_TIMESTAMP:
        SEQUENCE = (SEQUENCE + 1) & SEQUENCE_MASK
        if SEQUENCE == 0:
            timestamp = til_next_millis(LAST_TIMESTAMP)
    else:
        SEQUENCE = 0

    LAST_TIMESTAMP = timestamp
    timestamp = timestamp - (int(epoch * 1000))

    return (
        (timestamp << TIMESTAMP_LEFT_SHIFT)
        | (datacenter_id << DATACENTER_ID_SHIFT)
        | (worker_id << WORKER_ID_SHIFT)
        | SEQUENCE
    )
