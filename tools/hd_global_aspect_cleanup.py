"""One buffered global crop/aspect correction; derived artwork, never approval.

No Source stencil, palette remapping, contrast, per-letter fit or added pixels.
The fixed 10016 recipe keeps all alpha>=16 ink and discloses omitted low-alpha noise.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import struct

from PIL import Image, __version__ as PILLOW_VERSION

METHOD = "derived-10016-genuine-charcoal-single-global-aspect-refit-v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 4_194_304


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


SECURE_OPENAT_AVAILABLE = (os.name == "posix" and os.open in os.supports_dir_fd and
                           hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"))


def regular_bytes(path):
    """Read through authenticated directory descriptors, never a reopened path.

    The authoring helper requires secure POSIX openat; other platforms fail closed.
    This restriction does not affect the Windows game or its generated assets.
    """
    if not SECURE_OPENAT_AVAILABLE:
        raise ValueError("secure POSIX descriptor-relative input reads are required")
    path = Path(path).absolute()
    if ".." in path.parts or not path.name:
        raise ValueError("normalized regular input path required")
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    directories = []
    try:
        directories.append(os.open(path.anchor, directory_flags))
        for part in path.parts[1:-1]:
            directories.append(os.open(part, directory_flags, dir_fd=directories[-1]))
        parent = directories[-1]
        before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError("bounded regular nonsymlink input required")
        with os.fdopen(os.open(path.name, file_flags, dir_fd=parent), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_BYTES or identity(opened) != identity(before):
                raise ValueError("opened input changed or is not bounded regular data")
            payload = stream.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES or stream.read(1):
                raise ValueError("input exceeds bounded read")
            after = os.fstat(stream.fileno())
        final = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if identity(before) != identity(after) or identity(before) != identity(final):
            raise ValueError("input changed during buffered read")
        return payload
    except OSError as error:
        raise ValueError("secure input directory/file traversal rejected") from error
    finally:
        for descriptor in reversed(directories):
            os.close(descriptor)


def checked(binding, root):
    if type(binding) is not dict or set(binding) != {"path", "sha256"}:
        raise ValueError("exact portable path/SHA256 binding required")
    text, sha = binding["path"], binding["sha256"]
    if (type(text) is not str or not text or "\\" in text or ":" in text or
            PurePosixPath(text).is_absolute() or any(p in {"", ".", ".."} for p in text.split("/")) or
            type(sha) is not str or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha)):
        raise ValueError("unsafe path or invalid SHA256")
    payload = regular_bytes(Path(root) / text)
    if digest(payload) != sha:
        raise ValueError("input hash mismatch")
    return payload


def global_crop_refit(raw_payload, window, output_size, omitted_low_alpha):
    """Pure single crop then Lanczos refit using only verified parent bytes."""
    with Image.open(io.BytesIO(raw_payload)) as opened:
        if opened.format != "PNG" or max(opened.size) > 4096 or opened.width * opened.height > MAX_PIXELS:
            raise ValueError("bounded PNG parent required")
        raw = opened.convert("RGBA")
    if (type(window) is not list or len(window) != 4 or any(type(v) is not int for v in window) or
            type(output_size) is not list or len(output_size) != 2 or any(type(v) is not int for v in output_size) or
            type(omitted_low_alpha) is not int or omitted_low_alpha < 0):
        raise ValueError("integer crop/output/noise declarations required")
    x, y, w, h = window
    if not (x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= raw.width and y+h <= raw.height):
        raise ValueError("crop exceeds parent")
    if min(output_size) <= 0 or max(output_size) > 4096 or output_size[0] * output_size[1] > MAX_PIXELS:
        raise ValueError("output canvas exceeds bounds")
    alpha = raw.getchannel("A")
    outside = alpha.copy()
    outside.paste(0, (x, y, x+w, y+h))
    histogram = outside.histogram()
    if sum(histogram[16:]):
        raise ValueError("crop would discard occupied alpha>=16 parent ink")
    if sum(histogram[1:16]) != omitted_low_alpha:
        raise ValueError("omitted low-alpha noise count differs")
    fitted = raw.crop((x, y, x+w, y+h)).resize(tuple(output_size), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    fitted.save(buffer, format="PNG", compress_level=9)
    return buffer.getvalue(), dict(parent_canvas=list(raw.size), window=window,
        output_canvas=output_size, all_alpha16_ink_retained=True,
        omitted_alpha1_to15_samples=omitted_low_alpha,
        output_RGBA_sha256=digest(fitted.tobytes()),
        operation="one global crop then Lanczos aspect refit, no further pixel operations")


def run_recipe(recipe_path, root, output):
    output = Path(output)
    if output.exists():
        raise ValueError("fresh absent output directory required")
    rb = regular_bytes(recipe_path)
    recipe = json.loads(rb)
    fields = {"format_version", "method", "asset", "source", "palette", "parent_raw",
              "window", "output_size", "omitted_low_alpha", "pillow_version"}
    if (type(recipe) is not dict or set(recipe) != fields or type(recipe["format_version"]) is not int or
            recipe["format_version"] != 1 or recipe["method"] != METHOD or recipe["asset"] != "10016" or
            recipe["window"] != [0, 289, 2167, 130] or recipe["output_size"] != [2176, 128] or
            recipe["omitted_low_alpha"] != 100 or recipe["pillow_version"] != PILLOW_VERSION):
        raise ValueError("exact fixed10016 method/recipe/Pillow version required")
    source = checked(recipe["source"], root)
    palette = checked(recipe["palette"], root)
    raw = checked(recipe["parent_raw"], root)
    if (len(source) < 20 or list(struct.unpack_from("<5i", source)) != [0, 0, 8, 136, 8] or
            len(palette) != 768):
        raise ValueError("Original header or palette differs")
    png, detail = global_crop_refit(raw, recipe["window"], recipe["output_size"], recipe["omitted_low_alpha"])
    if detail["parent_canvas"] != [2167, 725]:
        raise ValueError("fixed10016 genuine parent canvas differs")
    execution = dict(status="success", method=METHOD, recipe_sha256=digest(rb),
        tool_sha256=digest(regular_bytes(__file__)), source_sha256={"10016": digest(source)},
        parent_raw_sha256=[digest(raw)], output_sha256={"10016": digest(png)})
    report = dict(execution=execution, geometry=detail, pillow_version=PILLOW_VERSION,
        original_palette_sha256=digest(palette), source_supplies_geometry_or_RGB=False,
        no_artistic_or_runtime_approval=True)
    # Validate every input and render in memory before publishing a fresh result.
    output.mkdir(parents=True, exist_ok=False)
    (output / "10016-derived.png").write_bytes(png)
    (output / "execution-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("hd_root", type=Path)
    parser.add_argument("fresh_output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_recipe(args.recipe, args.hd_root, args.fresh_output)["execution"], sort_keys=True))
