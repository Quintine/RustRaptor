"""Synthetic-only scalar model of the proposed opt-in kernel; no game/art IO."""
import math
import struct

def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]

def lanczos(value):
    if value == 0:
        return 1.0
    if abs(value) >= 3:
        return 0.0
    value *= math.pi
    return math.sin(value) / value * (math.sin(value / 3) / (value / 3))

def axis_weights(start, end, output):
    start, end = float(start), float(end)
    scale = max((end - start) / output, 1.0)
    rows = []
    for destination in range(output):
        center = start + (destination + 0.5) * (end - start) / output
        lower = max(math.floor(center - 3 * scale), math.floor(start))
        upper = min(math.ceil(center + 3 * scale), math.ceil(end))
        weights = []
        for index in range(lower, upper):
            overlap = max(0.0, min(index + 1, end) - max(index, start))
            weight = lanczos((index + 0.5 - center) / scale) * overlap
            if weight:
                weights.append((index, weight))
        total = sum(value for _, value in weights)
        if not math.isfinite(total) or abs(total) <= 1e-12:
            raise ValueError('invalid rational atlas filter weights')
        rows.append([(index, f32(value / total)) for index, value in weights])
    return rows

def sample_fractional(pixels, geometry):
    left, top, right, bottom = geometry['bounds']
    width, height = geometry['resident']
    _, first_y, _, last_y = geometry['pixels']
    x_weights = axis_weights(left, right, width)
    y_weights = axis_weights(top, bottom, height)
    horizontal = []
    for source_y in range(first_y, last_y):
        row = []
        for weights in x_weights:
            sample = [0.0] * 4
            for source_x, weight in weights:
                for channel in range(4):
                    sample[channel] = f32(sample[channel] + f32(pixels[source_y][source_x][channel] * weight))
            row.append(sample)
        horizontal.append(row)
    result = []
    for weights in y_weights:
        row = []
        for x in range(width):
            sample = [0.0] * 4
            for source_y, weight in weights:
                for channel in range(4):
                    sample[channel] = f32(sample[channel] + f32(horizontal[source_y - first_y][x][channel] * weight))
            row.append(tuple(math.floor(min(255, max(0, value)) + 0.5) for value in sample))
        result.append(row)
    return result
