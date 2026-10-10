#!/usr/bin/env python3
"""Compare complete JSONL gameplay snapshots, reporting the first state difference.

Both files must be recorded after the same complete simulation update. Property
order is ignored; entity and projectile list order is part of the contract.
Original data and generated traces belong in the ignored .reference directory.
"""
import argparse
import json
from pathlib import Path


def first_difference(left, right, path="state"):
    if type(left) is not type(right):
        return path, left, right
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return path + ".keys", sorted(left), sorted(right)
        for key in sorted(left):
            difference = first_difference(left[key], right[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(left, list):
        if len(left) != len(right):
            return path + ".length", len(left), len(right)
        for index, (a, b) in enumerate(zip(left, right)):
            difference = first_difference(a, b, f"{path}[{index}]")
            if difference:
                return difference
    elif left != right:
        return path, left, right
    return None


def read_trace(path):
    records = []
    with Path(path).open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or record.get("tick") != len(records) + 1:
                raise ValueError(f"{path}:{line_number}: expected consecutive tick {len(records) + 1}")
            records.append(record)
    if not records:
        raise ValueError(f"{path}: no snapshots")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("candidate")
    args = parser.parse_args()
    reference = read_trace(args.reference)
    candidate = read_trace(args.candidate)
    for tick, (left, right) in enumerate(zip(reference, candidate), 1):
        difference = first_difference(left, right)
        if difference:
            path, a, b = difference
            print(f"Divergence at tick {tick}: {path}")
            print(f"  reference: {a!r}")
            print(f"  candidate: {b!r}")
            return 1
    if len(reference) != len(candidate):
        print(f"Trace length differs: {len(reference)} reference steps, {len(candidate)} candidate steps")
        return 1
    print(f"Identical gameplay snapshots across {len(reference)} simulation steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
