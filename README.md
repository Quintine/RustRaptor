# RaptorReplica

[RustRaptor](RustRaptor/README.md) contains the independent Rust game, bundled mods,
SD/HD artwork, sound effects, schemas, tests and build tools. Rust is the default:

```sh
./play.sh
```

You can also run `./RustRaptor/run.sh`. The game loads your existing `data/`
catalog; choose bundled mods from its **Mods** menu. Mod images and sounds are
tracked in Git alongside their definitions and scripts.

The retained source under `raptor/` is an optional reference. It is not required
to build or play RustRaptor. `./play.sh --engine legacy` runs that reference.

See [Rust build and validation](RustRaptor/docs/rust-rewrite.md),
[modding API](RustRaptor/docs/modding-api.md), and
[Iron Coast packages](RustRaptor/docs/iron-coast.md).
