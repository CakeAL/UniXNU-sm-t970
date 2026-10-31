"""Minimal flattened-device-tree reader used by the SM-T970 host checks."""
import struct


class FdtError(ValueError):
    pass


def parse(blob):
    """Return (header, {node_path: {property: value}}) for an FDT blob."""
    if len(blob) < 40:
        raise FdtError('truncated FDT header')
    (magic, total, off_struct, off_strings, off_rsvmap, version, last_comp,
     boot_cpuid, size_strings, size_struct) = struct.unpack_from('>10I', blob, 0)
    if magic != 0xD00DFEED:
        raise FdtError('bad FDT magic')
    if total != len(blob):
        raise FdtError(f'FDT totalsize {total} differs from blob length {len(blob)}')
    if version < 16 or last_comp > version:
        raise FdtError('unsupported FDT version')
    strings = blob[off_strings:off_strings + size_strings]
    nodes = {}
    stack = []
    offset = off_struct
    end = off_struct + size_struct
    while offset + 4 <= end:
        token = struct.unpack_from('>I', blob, offset)[0]
        offset += 4
        if token == 1:  # BEGIN_NODE
            zero = blob.index(b'\0', offset)
            name = blob[offset:zero].decode('utf-8', 'replace')
            offset = (zero + 4) & ~3
            stack.append(name if stack else '')
            nodes.setdefault('/' + '/'.join(stack[1:]), {})
        elif token == 2:  # END_NODE
            if not stack:
                raise FdtError('unbalanced END_NODE')
            stack.pop()
        elif token == 3:  # PROP
            length, name_offset = struct.unpack_from('>II', blob, offset)
            offset += 8
            zero = strings.index(b'\0', name_offset)
            name = strings[name_offset:zero].decode('utf-8', 'replace')
            value = blob[offset:offset + length]
            offset = (offset + length + 3) & ~3
            nodes['/' + '/'.join(stack[1:])][name] = value
        elif token == 4:  # NOP
            continue
        elif token == 9:  # END
            break
        else:
            raise FdtError(f'unknown FDT token {token:#x}')
    header = {'total': total, 'version': version, 'boot_cpuid': boot_cpuid,
              'reserved_map_entries': reserved_entries(blob, off_rsvmap)}
    return header, nodes


def reserved_entries(blob, offset):
    count = 0
    while offset + 16 <= len(blob):
        address, size = struct.unpack_from('>QQ', blob, offset)
        if address == 0 and size == 0:
            break
        count += 1
        offset += 16
    return count


def strings(value):
    return [s.decode('utf-8', 'replace') for s in value.split(b'\0') if s]


def cells(blob_value):
    if len(blob_value) % 4:
        raise FdtError('cell property is not 4-byte aligned')
    return list(struct.unpack('>' + 'I' * (len(blob_value) // 4), blob_value))


def reg_ranges(blob_value, address_cells=2, size_cells=2):
    values = cells(blob_value)
    stride = address_cells + size_cells
    if len(values) % stride:
        raise FdtError('reg property has an unexpected cell count')
    ranges = []
    for i in range(0, len(values), stride):
        address = 0
        for value in values[i:i + address_cells]:
            address = (address << 32) | value
        size = 0
        for value in values[i + address_cells:i + stride]:
            size = (size << 32) | value
        ranges.append((address, size))
    return ranges
