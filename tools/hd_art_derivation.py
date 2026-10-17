"""Read-only lineage checks for explicitly cleaned imagegen artwork.

This records how reviewed pixels were made; it does not grant artistic approval
or execute a recipe. Jobs without an artwork_derivation remain unchanged.
"""
import hashlib
import json
from pathlib import Path
import re


def checked_file(root, reference):
    if (not isinstance(reference, dict) or set(reference) != {"path", "sha256"}
            or not isinstance(reference["path"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(reference["sha256"]))):
        raise ValueError("derivation needs an exact path/SHA-256 reference")
    relative = Path(reference["path"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("derivation reference must be a portable relative path")
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("derivation reference escapes its root or is not a file")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != reference["sha256"]:
        raise ValueError(f"derivation file changed: {relative}")
    return payload


def checked_json(root, reference):
    value = json.loads(checked_file(root, reference))
    if not isinstance(value, dict):
        raise ValueError("derivation JSON must contain an object")
    return value


def validate_derivation(root, project, candidate, review, rows, qa):
    reference = candidate.get("artwork_derivation")
    if reference is None:
        if "artwork_derivation" in candidate or "artwork_derivation" in review:
            raise ValueError("derivation cannot be null or present only in review")
        return None
    if review.get("artwork_derivation") != reference:
        raise ValueError("artistic review does not bind this derivation")
    lineage = checked_json(root, reference)
    if (type(lineage.get("format_version")) is not int or lineage["format_version"] != 1
            or lineage.get("kind") != "deterministic_cleanup"
            or not isinstance(lineage.get("method"), str) or not lineage["method"].strip()):
        raise ValueError("unsupported or unnamed artwork derivation")
    parents = lineage.get("parents")
    if not isinstance(parents, list) or not parents:
        raise ValueError("derivation needs original imagegen parents")
    for parent in parents:
        if not isinstance(parent, dict) or set(parent) != {"raw_png", "imagegen_receipt", "prompt"}:
            raise ValueError("derivation parent needs raw PNG, imagegen receipt and prompt")
        if not checked_file(root, parent["raw_png"]).startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("derivation parent is not a PNG")
        # Preserve the actual receipt verbatim. Its historical format is not
        # rewritten to pretend that cleanup was another generator invocation.
        checked_json(root, parent["imagegen_receipt"])
        if not checked_file(root, parent["prompt"]).strip():
            raise ValueError("derivation parent prompt is empty")
    tools = lineage.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("derivation needs a checked-in cleanup tool")
    for tool in tools:
        checked_file(project, tool)
        if Path(tool["path"]).parts[0] != "tools" or Path(tool["path"]).suffix != ".py":
            raise ValueError("derivation tool must be a project tools Python file")
    checked_json(root, lineage.get("recipe"))
    execution = checked_json(root, lineage.get("execution_receipt")).get("execution", {})
    if not isinstance(execution, dict):
        raise ValueError("derivation execution must contain an object")
    if lineage.get("sources") != {asset: frame["source_sha256"] for asset, frame in rows.items()}:
        raise ValueError("derivation Source inventory differs from selected artwork")
    files = {frame["file"] for frame in rows.values()}
    outputs = lineage.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != files:
        raise ValueError("derivation output inventory differs from selected artwork")
    for path, sha in outputs.items():
        payload = checked_file(root, {"path": path, "sha256": sha})
        if not payload.startswith(b"\x89PNG\r\n\x1a\n") or qa.get("artwork_sha256", {}).get(path) != sha:
            raise ValueError("derivation output differs from runtime-reviewed PNG")
    if (execution.get("status") != "success" or execution.get("method") != lineage["method"]
            or execution.get("recipe_sha256") != lineage["recipe"]["sha256"]
            or execution.get("tool_sha256") not in {tool["sha256"] for tool in tools}
            or execution.get("source_sha256") != lineage["sources"]
            or execution.get("parent_raw_sha256") != sorted({p["raw_png"]["sha256"] for p in parents})
            or execution.get("output_sha256") != {asset: outputs[frame["file"]] for asset, frame in rows.items()}):
        raise ValueError("derivation execution does not bind actual recipe, tool, inputs and outputs")
    return reference
