# SPDX-License-Identifier: GPL-2.0-or-later
"""Read LevelDB table files (.ldb) in pure Python, including a minimal Snappy decompressor.

Used to read Synapse 4's IndexedDB without extra packages.
"""
import struct


def varint(buf, pos):
    result = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, pos


def snappy_decompress(buf):
    _, pos = varint(buf, 0)
    out = bytearray()
    while pos < len(buf):
        tag = buf[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:  # literal
            length = tag >> 2
            if length >= 60:
                extra = length - 59
                length = int.from_bytes(buf[pos:pos + extra], 'little')
                pos += extra
            length += 1
            out += buf[pos:pos + length]
            pos += length
            continue
        if kind == 1:
            length = ((tag >> 2) & 7) + 4
            offset = ((tag >> 5) << 8) | buf[pos]
            pos += 1
        elif kind == 2:
            length = (tag >> 2) + 1
            offset = int.from_bytes(buf[pos:pos + 2], 'little')
            pos += 2
        else:
            length = (tag >> 2) + 1
            offset = int.from_bytes(buf[pos:pos + 4], 'little')
            pos += 4
        for _ in range(length):
            out.append(out[-offset])
    return bytes(out)


def read_block(data, offset, size):
    raw = data[offset:offset + size]
    compressed = data[offset + size] == 1
    return snappy_decompress(raw) if compressed else raw


def block_entries(block):
    restarts = struct.unpack('<I', block[-4:])[0]
    end = len(block) - 4 - 4 * restarts
    pos = 0
    key = b''
    while pos < end:
        shared, pos = varint(block, pos)
        unshared, pos = varint(block, pos)
        value_len, pos = varint(block, pos)
        key = key[:shared] + block[pos:pos + unshared]
        pos += unshared
        value = block[pos:pos + value_len]
        pos += value_len
        yield key, value


def table_entries(data):
    footer = data[-48:]
    _, pos = varint(footer, 0)  # metaindex handle
    _, pos = varint(footer, pos)
    index_offset, pos = varint(footer, pos)
    index_size, _ = varint(footer, pos)
    for _, handle in block_entries(read_block(data, index_offset, index_size)):
        offset, pos = varint(handle, 0)
        size, _ = varint(handle, pos)
        yield from block_entries(read_block(data, offset, size))
