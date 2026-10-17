# Shared HD generation workflow

Prepare and inspect every source reference, check the palette binding, and save the complete prompt before acquiring a slot. Acquire only when ready to submit. A slot must never cover local preparation, a model turn, artwork copying or visual review.

Use **one `functions.exec` orchestration** for acquire → start → built-in imagegen → outcome report. Submit only when acquisition succeeds and `start.changed` is `true`. Run the report immediately after the awaited tool returns or throws, before returning the result to the model. Then copy the saved raw PNG unchanged and perform artistic/runtime review. Successful generation does not mean accepted artwork.

Observed built-in successes have `image_url` and `output_hint` keys. `image_url` contains a PNG data URL; never print or serialize it to a log. `output_hint` identifies the saved raw PNG. Observed connection failures throw `image generation failed: connection failed: error sending request`. Also check returned `isError`, textual error fields and unexpected result shapes; a nonthrowing failure is still a failure.

The following skeleton runs inside `functions.exec`. `preparedArguments`, `owner`, `job`, `gatePath`, `projectRoot` and `errorFile` must already be known. Shell arguments are quoted individually; the error file is written without evaluating its contents.

```javascript
const quote = s => "'" + String(s).replaceAll("'", "'\"'\"'") + "'";
async function gate(...args) {
  const r = await tools.exec_command({
    cmd: ["python3", gatePath, ...args].map(quote).join(" "),
    workdir: projectRoot, max_output_tokens: 800
  });
  if (r.exit_code !== 0) throw new Error("Generation gate command failed");
  return JSON.parse(r.output);
}
const lease = await gate("acquire", "--owner", owner, "--job", job);
if (!lease.acquired) { text(lease); exit(); }
const started = await gate("start", "--owner", owner, "--lease", lease.lease_id);
if (!started.changed) {
  if (["admissions_paused", "active_request_accounting_over_capacity"].includes(started.reason)) {
    // This newly acquired reservation has not submitted a request.
    text(await gate("release", "--owner", owner, "--lease", lease.lease_id));
  }
  text(started); exit();
}
let result, outcome = "failure", errorText = "";
try {
  result = await tools.image_gen__imagegen(preparedArguments);
  const returnedError = result?.error?.message || result?.error || result?.message;
  if (result?.isError || returnedError) {
    errorText = typeof returnedError === "string" ? returnedError :
      result?.content?.filter(x => x.type === "text").map(x => x.text).join("\n") ||
      "Built-in imagegen returned an error";
  } else if (typeof result?.image_url === "string" &&
             result.image_url.startsWith("data:image/") &&
             typeof result?.output_hint === "string") {
    outcome = "success";
  } else {
    errorText = "Unexpected built-in imagegen result shape";
  }
} catch (error) {
  errorText = String(error?.message || error);
} finally {
  if (/connection failed|error sending request/i.test(errorText)) outcome = "connection_failure";
  const reportArgs = ["report", "--owner", owner, "--lease", lease.lease_id,
                      "--outcome", outcome];
  if (errorText) {
    const code = "from pathlib import Path; import sys; Path(sys.argv[1]).write_text(sys.argv[2])";
    const written = await tools.exec_command({
      cmd: ["python3", "-c", code, errorFile, errorText].map(quote).join(" "),
      workdir: projectRoot, max_output_tokens: 200
    });
    if (written.exit_code !== 0) throw new Error("Could not save imagegen error; retain lease for recovery");
    reportArgs.push("--error-file", errorFile);
  }
  text(await gate(...reportArgs));
}
if (outcome === "success") generatedImage(result);
```

The four-slot gate retains started requests and old requests with unknown status until explicit completion or recovery. Only unstarted reservations expire after thirty minutes plus a two-minute grace period. `start` refuses duplicate starts, unknown legacy requests, paused admissions and over-capacity accounting. A restored unknown request is immediately flagged for owner attention. No gate command starts, stops or terminates an imagegen tool.

After interruption, recover the original yielded cell or saved result before any new submission. Report a recovered completion, or release a reservation only after confirming no request was submitted/running. Do not infer completion from age. `status` reads lease phases, ages, admission state and recent outcomes without changing reservations. Root can pause new admissions while reconciling unknown calls; existing calls may still finish and report. Eligibility currently uses the first available slot with one request per owner, without a FIFO queue.

Exact sanitized service errors and UTC report times stay in ignored `data/hd/jobs/.imagegen-gate/events.jsonl`. Connection failures impose a 60–600-second cooldown and at most three failures per job in a thirty-minute retry batch. During denial or cooldown, prepare or review another job. Do not replace a failed remaster with scaled original art.

## Registering reviewed standalone terrain

`hd_register_reviewed.py` accepts an explicit `complete_standalone_selection`
only for a `Terrain` / `contextual_terrain_shard` job. This selection contains
complete one-frame definitions, with `frame_count = 1` and `frame = 0`; it cannot
approve part of an animation. `complete_family` must remain false. Its
`full_inventory`, `selected_assets` and `original_fallback_assets` must describe
the complete original shard and a disjoint, exhaustive partition. Fallback IDs
retain their outstanding status and cannot silently retain a previous HD binding.

Each selected ID needs an independent material decision bound to its exact source,
raw PNG and renderer fields, plus current loader evidence at scales 1–4. The full
inventory is checked against original catalog terrain ranges, payloads, palette,
canvas and origins. A separate independent context receipt binds the combined
selection, baseline, future projection and closed changed-case proof. Registration
and queue approval reject missing, stale or unrelated evidence. Whole animation
families continue to require every original frame.

Run the tool regression checks with
`python3 -m unittest discover -s tools -p 'test_hd_*.py'`. They include successful
registration of separately approved selections and rejection of incomplete
animations, held material, inconsistent inventory, stale artifacts and incorrect
context bindings.

Existing Terrain siblings may be carried through a new selection with the opt-in
`standalone-terrain-carried-identity-v2` contract. The selected, carried and
Original-fallback sets must partition the full original job inventory. Carried
definitions must already be complete one-frame Terrain entries in the current
canonical manifest; their complete fields, optional policies, raw bytes and
authenticated prior registration/runtime receipts must match exactly. Multiple
prior registration records are supported. Carrying never approves, inserts or
overwrites those definitions, and grants no approval to newly selected artwork.
New selections still need their own current all-scale, material and context
evidence. The older Master74 contract remains supported unchanged.

A genuinely new single-picture generation job can instead declare its actual
complete one-picture inventory. It must not claim that an earlier multi-picture
generation had a smaller inventory or use this route to split an animation.

The portable carried-identity and frame-policy checks also run with
`python3 -m unittest discover -s tests -p 'test_hd_*.py'`.
