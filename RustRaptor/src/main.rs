use anyhow::{Context, Result};
use raptor_replica::{
    assets::{Catalog, decode_demo},
    content::{ContentId, Registry},
    modding::{self, ActiveMods},
    persistence::{Paths, Pilot},
    simulation::{Input, World},
};
use std::path::PathBuf;
fn main() {
    if let Err(e) = run() {
        eprintln!("{e:#}");
        std::process::exit(1)
    }
}
fn run() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let arg = |key: &str| {
        args.iter()
            .position(|s| s == key)
            .and_then(|i| args.get(i + 1))
    };
    let benchmark = args.iter().any(|a| a == "--benchmark");
    anyhow::ensure!(
        !benchmark || arg("--smoke-frames").is_some(),
        "--benchmark requires --smoke-frames"
    );
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "raptor-rust [--data DIR] [--mods DIR]\n  --verify-assets             Check catalog and all original mission definitions\n  --validate-hd               Validate every supplied original-content HD frame\n  --validate-mods ID,...      Validate selected local mod packages\n  --schemas DIR              Write mod API JSON schemas\n  --headless MISSION --ticks N  Deterministic simulation smoke run\n  --replay ASSET_NAME --trace FILE  Record legacy demo simulation states\n  --import-legacy FILE --output FILE\n  --smoke-frames N             Exit desktop after N rendered frames\n  --benchmark                 Report startup and frame timings (with --smoke-frames)\n  --screenshot FILE           Save the final desktop frame as PNG\n  --preview-mission ID         Start a mission directly\n  --preview-cinematic KIND     credits, intro, landing, death, end1, end2, end3\n  --profile-root DIR           Use a separate pilot/config/cache directory\n  --enabled ID,...             Enable mods for headless/replay commands"
        );
        return Ok(());
    }
    if let Some(path) = arg("--schemas") {
        modding::write_schemas(&PathBuf::from(path))?;
        println!("Wrote API v1 schemas to {path}");
        return Ok(());
    }
    let package = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let data = arg("--data").map(PathBuf::from).unwrap_or_else(|| {
        if package.join("data/INDEX").is_file() {
            package.join("data")
        } else {
            package.join("../data")
        }
    });
    let catalog = Catalog::open(data)?;
    if args.iter().any(|a| a == "--validate-hd") {
        let hd_root = catalog.root.join("hd");
        anyhow::ensure!(
            hd_root.join("hd.json").is_file(),
            "no HD pack at {}",
            hd_root.display()
        );
        let mut hd = raptor_replica::hd::HdAssets::load_lazy(&hd_root, &catalog, None);
        let report = hd.validate_all();
        println!(
            "HD pack: {} registered, {} validated, {} rejected supplied frames",
            report.registered, report.validated, report.rejected
        );
        for diagnostic in &hd.diagnostics {
            eprintln!("HD: {diagnostic}");
        }
        anyhow::ensure!(
            report.registered > 0 && report.validated == report.registered && report.rejected == 0,
            "HD pack validation failed"
        );
        return Ok(());
    }
    let base = Registry::base(&catalog)?;
    if args.iter().any(|a| a == "--verify-assets") {
        println!(
            "Verified {} assets; {} missions, {} enemies, {} weapons, {} items",
            catalog.verify()?,
            base.missions.len(),
            base.enemies.len(),
            base.weapons.len(),
            base.items.len()
        );
        return Ok(());
    }
    let mut paths = Paths::discover()?;
    if let Some(root) = arg("--profile-root") {
        let root = PathBuf::from(root);
        paths.data = root.join("data");
        paths.config = root.join("config");
        paths.cache = root.join("cache");
        paths.legacy = root.join("legacy");
    }
    let root = arg("--mods").map(PathBuf::from).unwrap_or_else(|| {
        if paths.mods().is_dir() {
            paths.mods()
        } else {
            package.join("mods")
        }
    });
    let discovery = modding::discover(&root);
    if let Some(ids) = arg("--validate-mods") {
        let enabled = ids
            .split(',')
            .filter(|s| !s.is_empty())
            .map(str::to_string)
            .collect::<Vec<_>>();
        let active = ActiveMods::build(&base, &discovery, &enabled, Some(&catalog))?;
        println!(
            "Validated {} mods; {} override(s)",
            active.pins.len(),
            active.registry.overrides.len()
        );
        for err in discovery.errors {
            eprintln!("Discovery: {err}");
        }
        return Ok(());
    }
    if let Some(path) = arg("--import-legacy") {
        let output = PathBuf::from(arg("--output").context("--import-legacy requires --output")?);
        let source = PathBuf::from(path).canonicalize()?;
        anyhow::ensure!(
            output.canonicalize().ok().as_ref() != Some(&source),
            "legacy import output must be separate from the original save"
        );
        let pilot = Pilot::import_legacy(&PathBuf::from(path), &base)?;
        pilot.save(&output)?;
        println!("Imported pilot to {}", output.display());
        return Ok(());
    }
    let enabled = arg("--enabled")
        .map(|s| {
            s.split(',')
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    if let Some(id) = arg("--headless") {
        let mut active = ActiveMods::build(&base, &discovery, &enabled, Some(&catalog))?;
        let mut pilot = Pilot::default();
        pilot.mission = ContentId::new(id)?;
        let mut world = World::new(&pilot.mission, &pilot, &active.registry)?;
        let ticks = arg("--ticks")
            .map(|s| s.parse())
            .transpose()?
            .unwrap_or(500);
        for _ in 0..ticks {
            world.step(
                Input {
                    fire: true,
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )?;
            if world.outcome != raptor_replica::simulation::Outcome::Playing {
                break;
            }
        }
        println!(
            "tick={} outcome={:?} enemies={} credits={} digest={}",
            world.tick,
            world.outcome,
            world.enemies.len(),
            world.player.credits,
            world.digest()
        );
        return Ok(());
    }
    if let Some(name) = arg("--replay") {
        let (sector, wave, frames) = decode_demo(&catalog.named(name)?)?;
        let mission = ContentId(format!("base:sector_{}_wave_{}", sector + 1, wave + 1));
        let mut pilot = Pilot::demo(sector, &base)?;
        pilot.mission = mission.clone();
        let mut active = ActiveMods::build(&base, &discovery, &enabled, Some(&catalog))?;
        let mut world = World::new(&mission, &pilot, &active.registry)?;
        let mut trace = arg("--trace")
            .map(|path| std::fs::File::create(path))
            .transpose()?;
        let limit = arg("--ticks")
            .map(|s| s.parse::<usize>())
            .transpose()?
            .unwrap_or(frames.len());
        for f in frames.into_iter().take(limit) {
            world.step(
                Input {
                    fire: f.buttons[0],
                    cycle: f.buttons[1],
                    bomb: f.buttons[2],
                    absolute: Some([f.x as i32, f.y as i32]),
                    demo_bank: Some(f.bank as i32),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )?;
            if let Some(file) = &mut trace {
                use std::io::Write;
                writeln!(file, "{}", world.reference_state(&active.registry))?;
            }
        }
        println!("Replay tick={} digest={}", world.tick, world.digest());
        return Ok(());
    }
    #[cfg(feature = "desktop")]
    {
        let movie = arg("--preview-cinematic")
            .map(|s| match s.as_str() {
                "credits" => Ok(raptor_replica::cinematics::Kind::OpeningCredits),
                "intro" => Ok(raptor_replica::cinematics::Kind::Intro),
                "landing" => Ok(raptor_replica::cinematics::Kind::Landing),
                "death" => Ok(raptor_replica::cinematics::Kind::Death),
                "end1" => Ok(raptor_replica::cinematics::Kind::CampaignEnd(0)),
                "end2" => Ok(raptor_replica::cinematics::Kind::CampaignEnd(1)),
                "end3" => Ok(raptor_replica::cinematics::Kind::CampaignEnd(2)),
                _ => Err(anyhow::anyhow!("unknown cinematic {s}")),
            })
            .transpose()?;
        raptor_replica::desktop::run(
            catalog,
            base,
            paths,
            root,
            arg("--smoke-frames").map(|s| s.parse()).transpose()?,
            arg("--screenshot").map(PathBuf::from),
            arg("--preview-mission")
                .map(|s| ContentId::new(s))
                .transpose()?,
            movie,
            benchmark,
        )?;
    }
    #[cfg(not(feature = "desktop"))]
    {
        let _ = (catalog, base, paths, root, benchmark);
        return Err(anyhow::anyhow!(
            "desktop support is disabled; use a headless command"
        ));
    }
    #[cfg(feature = "desktop")]
    Ok(())
}
