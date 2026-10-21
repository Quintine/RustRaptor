# RustRaptor v1.0.0

Self-contained Linux x86_64 and Windows x86_64 packages, with original game data, the classic intro and sound, the in-game mod manager and all 45 bundled mods. Includes both Iron Coast stages, their 14 missions, bosses, weapons and original music, plus SD/HD mission briefings.

**HD artwork note: 5,743 of 5,753 original pictures have approved HD remasters. Ten pictures retain their original graphics. This release does not claim complete HD coverage.** The remaining IDs are `1035b`, `1035c`, `1035d`, `1035e`, `300a1`, `301ae`, `40374`, `404d2`, `4050b` and `40512`. Original and crisp scaling modes remain available; HD art does not alter collision dimensions or simulation.

This release keeps the gameplay, mod content and artwork from the tested 20 October preview, with freshly rebuilt version 1.0.0 Linux and Windows executables. No new artwork was generated for this release.

## Download and install

Download `Install-Windows.ps1` or `Install-Linux.sh` from this release and run it in a directory without an existing `RustRaptor` folder:

- Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Windows.ps1`
- Linux: `bash ./Install-Linux.sh` (the optional download helper needs Bash and Python 3.8+; the game does not require Python).

The helper downloads your platform ZIP and all seven shared-data ZIPs, checks archive and payload SHA-256 hashes, and assembles one portable folder. Start `RustRaptor/run.cmd` or `RustRaptor/run.sh`. Saves and settings stay in the separate `RaptorReplica` user profile directories.

For manual installation, download one platform ZIP plus every `RustRaptor-data-NN-of-07.zip` from this release. Compare with `SHA256SUMS`, then extract all eight archives into the same parent directory. Every ZIP starts with `RustRaptor/`. Use the Windows helper for reliable long-path extraction of retained artwork-review files.

Allow roughly 13 GB free for the installed folder and one temporary download. The complete shared data contains 32,373 files / 10,376,039,515 bytes. Original assets, accepted HD artwork and bundled mod graphics, sound and music are included. No compiler or old C++ engine is required.

Broader playtesting remains useful; the included validation covers its documented scenarios and is not a new full playthrough of every mission.
