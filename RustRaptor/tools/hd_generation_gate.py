#!/usr/bin/env python3
"""Coordinate four advisory built-in imagegen submissions across HD workers.

No API call is started or terminated by this tool. Leases last thirty minutes,
may be renewed while a tool yields, and are released with the actual outcome.
Workers without a lease should prepare/review other jobs, then try again.
"""
import argparse
import collections
import datetime
import fcntl
import json
import os
import re
import time
import uuid
from pathlib import Path

CAPACITY = 4
LEASE_SECONDS = 30 * 60
EXPIRY_GRACE_SECONDS = 2 * 60
RETRY_WINDOW_SECONDS = 30 * 60
MAX_JOB_CONNECTION_FAILURES = 3


def utc(seconds):
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).isoformat(timespec="seconds")


def sanitized_error(message):
    """Preserve the service text apart from credentials or embedded image data."""
    message = re.sub(r"data:image/[^;,\s]+;base64,[A-Za-z0-9+/=]+", "<image-data-redacted>", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]{16,}\b", "<api-key-redacted>", message)
    message = re.sub(r"(?i)(\bBearer\s+)[A-Za-z0-9._~-]+", r"\1<credential-redacted>", message)
    message = re.sub(r"(?i)([?&](?:api_key|apikey|access_token|token|signature)=)[^&\s]+", r"\1<credential-redacted>", message)
    return message


def write_atomic(path, value):
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def status(directory, now=None):
    """Read lease ages and recent outcomes without expiring or changing leases."""
    now = time.time() if now is None else now
    path = directory / "state.json"
    if not path.is_file():
        return {"action": "status", "capacity": CAPACITY, "active_reservations": 0,
                "leases": [], "recent_outcomes": {}}
    with (directory / "gate.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        state = json.loads(path.read_text())
        if state.get("format_version") != 1:
            raise ValueError("unsupported gate state; do not erase active reservations")
        leases = [{"lease_id": identity, "owner": lease["owner"],
                   "job_id": lease["job_id"],
                   "age_seconds": max(0, int(now - lease["created_epoch"])),
                   "expires_at": utc(lease["expires_epoch"]),
                   "renewal_needed": now >= lease["expires_epoch"],
                   "stale_reservation": now > lease["expires_epoch"] + EXPIRY_GRACE_SECONDS}
                  for identity, lease in state["leases"].items()]
        recent = []
        log = directory / "events.jsonl"
        if log.is_file():
            for line in log.read_text().splitlines():
                event = json.loads(line)
                stamp = datetime.datetime.fromisoformat(event["timestamp_utc"]).timestamp()
                if stamp >= now - RETRY_WINDOW_SECONDS:
                    recent.append(event)
        outcomes = collections.Counter(event["outcome"] for event in recent
                                       if event["event"] == "report")
        acquired = collections.Counter(event["owner"] for event in recent
                                       if event["event"] == "acquired")
        return {"action": "status", "timestamp_utc": utc(now), "capacity": CAPACITY,
                "active_reservations": len(leases), "leases": leases,
                "cooldowns": [{"owner": owner, "remaining_seconds": int(row["cooldown_until"] - now)}
                              for owner, row in state["owners"].items()
                              if row.get("cooldown_until", 0) > now],
                "recent_outcomes": dict(outcomes), "recent_acquisitions_by_owner": dict(acquired),
                "last_event": recent[-1] if recent else None,
                "fairness": "One lease per owner; eligible callers acquire the first available slot. No FIFO wait queue.",
                "limitation": "A reservation age does not prove the imagegen tool is running; ask its owner before changing an active request."}


def operate(directory, action, owner, job=None, lease_id=None, outcome=None, error=None, now=None):
    now = time.time() if now is None else now
    if not owner or len(owner) > 128 or any(char in owner for char in "\r\n\0"):
        raise ValueError("invalid owner identity")
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "gate.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "state.json"
        state = json.loads(path.read_text()) if path.is_file() else {"format_version": 1, "leases": {}, "owners": {}, "job_failures": {}}
        if state.get("format_version") != 1:
            raise ValueError("unsupported gate state; do not erase active reservations")
        events = []
        for identity, lease in list(state["leases"].items()):
            if now > lease["expires_epoch"] + EXPIRY_GRACE_SECONDS:
                del state["leases"][identity]
                events.append({"event": "expired_stale_reservation", "lease_id": identity, "owner": lease["owner"], "job_id": lease["job_id"], "previous_expiry": utc(lease["expires_epoch"]), "note": "Reservation expiry only; no running imagegen call was interrupted."})
        response = {"action": action, "owner": owner, "capacity": CAPACITY}
        if action == "acquire":
            if not job or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", job):
                raise ValueError("valid job ID required")
            if any(lease["owner"] == owner for lease in state["leases"].values()):
                response.update(acquired=False, reason="owner_already_has_inflight_reservation")
            elif any(lease["job_id"] == job for lease in state["leases"].values()):
                response.update(acquired=False, reason="job_already_reserved")
            else:
                owner_state = state["owners"].get(owner, {})
                failure_key = owner + "|" + job
                failures = [stamp for stamp in state["job_failures"].get(failure_key, []) if now - stamp < RETRY_WINDOW_SECONDS]
                state["job_failures"][failure_key] = failures
                if len(failures) >= MAX_JOB_CONNECTION_FAILURES:
                    response.update(acquired=False, reason="job_connection_retry_batch_exhausted", retry_after_seconds=max(1, int(failures[0] + RETRY_WINDOW_SECONDS - now)))
                elif owner_state.get("cooldown_until", 0) > now:
                    response.update(acquired=False, reason="connection_failure_cooldown", retry_after_seconds=max(1, int(owner_state["cooldown_until"] - now)))
                elif len(state["leases"]) >= CAPACITY:
                    response.update(acquired=False, reason="all_four_submission_slots_reserved")
                else:
                    identity = str(uuid.uuid4())
                    lease = {"owner": owner, "job_id": job, "created_epoch": now, "expires_epoch": now + LEASE_SECONDS}
                    state["leases"][identity] = lease
                    response.update(acquired=True, lease_id=identity, expires_at=utc(lease["expires_epoch"]), renewal_command=f"renew --owner {owner} --lease {identity}")
                    events.append({"event": "acquired", "lease_id": identity, "owner": owner, "job_id": job, "expires_at": utc(lease["expires_epoch"])})
        else:
            lease = state["leases"].get(lease_id)
            if lease is None:
                response.update(changed=False, reason="reservation_missing_or_expired")
            elif lease["owner"] != owner:
                raise ValueError("reservation belongs to another worker")
            elif action == "renew":
                lease["expires_epoch"] = now + LEASE_SECONDS
                response.update(changed=True, expires_at=utc(lease["expires_epoch"]))
                events.append({"event": "renewed", "lease_id": lease_id, "owner": owner, "job_id": lease["job_id"], "expires_at": utc(lease["expires_epoch"])})
            else:
                del state["leases"][lease_id]
                event = {"event": action, "lease_id": lease_id, "owner": owner, "job_id": lease["job_id"]}
                response.update(changed=True)
                if action == "report":
                    event["outcome"] = outcome
                    if error is not None:
                        event["sanitized_error"] = sanitized_error(error)
                    owner_state = state["owners"].setdefault(owner, {})
                    failure_key = owner + "|" + lease["job_id"]
                    if outcome == "connection_failure":
                        failures = [stamp for stamp in state["job_failures"].get(failure_key, []) if now - stamp < RETRY_WINDOW_SECONDS]
                        failures.append(now)
                        state["job_failures"][failure_key] = failures
                        streak = min(owner_state.get("consecutive_connection_failures", 0) + 1, 10)
                        cooldown = min(60 * 2 ** (streak - 1), 600)
                        owner_state.update(consecutive_connection_failures=streak, cooldown_until=now + cooldown)
                        response.update(retry_after_seconds=cooldown, job_connection_failures_in_batch=len(failures), retry_batch_exhausted=len(failures) >= MAX_JOB_CONNECTION_FAILURES)
                    elif outcome == "success":
                        state["owners"][owner] = {"consecutive_connection_failures": 0, "cooldown_until": 0}
                        state["job_failures"].pop(failure_key, None)
                events.append(event)
        response["active_reservations"] = len(state["leases"])
        response["prepare_other_jobs_when_waiting"] = True
        write_atomic(path, state)
        with (directory / "events.jsonl").open("a") as log:
            for event in events:
                log.write(json.dumps({"timestamp_utc": utc(now), **event}, ensure_ascii=False) + "\n")
        return response


def main():
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["acquire", "renew", "release", "report", "status"])
    parser.add_argument("--owner")
    parser.add_argument("--job")
    parser.add_argument("--lease")
    parser.add_argument("--outcome", choices=["success", "connection_failure", "failure"])
    parser.add_argument("--error-file", type=Path, help="UTF-8 service error; credential/image data is redacted, other text preserved")
    parser.add_argument("--directory", type=Path, default=project.parent / "data/hd/jobs/.imagegen-gate")
    args = parser.parse_args()
    if args.action == "status":
        print(json.dumps(status(args.directory), indent=2))
        return
    if not args.owner:
        parser.error("owner required for lease changes")
    if args.action != "acquire" and not args.lease:
        parser.error("lease ID required")
    if args.action == "report" and not args.outcome:
        parser.error("report needs an actual outcome")
    error = None
    if args.error_file:
        if args.error_file.stat().st_size > 64 * 1024:
            parser.error("error file exceeds64KiB; remove embedded payloads before logging")
        error = args.error_file.read_text()
    print(json.dumps(operate(args.directory, args.action, args.owner, args.job, args.lease, args.outcome, error), indent=2))


if __name__ == "__main__":
    main()
