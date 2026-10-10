use raptor_replica::{
    mod_selection::{plan_disable, plan_enable},
    modding::{self, Discovery, InstalledMod, Manifest},
};
use std::{collections::BTreeMap, path::PathBuf};

fn ids(values: &[&str]) -> Vec<String> {
    values.iter().map(|id| (*id).into()).collect()
}
fn package(id: &str, dependencies: &[(&str, &str)]) -> InstalledMod {
    InstalledMod {
        root: PathBuf::from(id),
        hash: String::new(),
        manifest: Manifest {
            id: id.into(),
            name: id.into(),
            version: "1.0.0".into(),
            api_version: 1,
            description: String::new(),
            content: "content.json".into(),
            scripts: vec![],
            conflicts: vec![],
            dependencies: dependencies
                .iter()
                .map(|(id, req)| ((*id).into(), (*req).into()))
                .collect(),
        },
    }
}
fn graph() -> Discovery {
    Discovery {
        mods: BTreeMap::from([
            ("shared".into(), package("shared", &[])),
            ("weapon".into(), package("weapon", &[("shared", "^1")])),
            ("enemy".into(), package("enemy", &[("shared", "^1")])),
            (
                "mission".into(),
                package("mission", &[("weapon", "^1"), ("enemy", "^1")]),
            ),
            ("sequel".into(), package("sequel", &[("mission", "^1")])),
            ("other".into(), package("other", &[])),
        ]),
        ..Default::default()
    }
}
#[test]
fn enabling_a_mission_selects_recursive_shared_dependencies_once() {
    let selected = ids(&["other"]);
    let planned = plan_enable(&graph(), &selected, "mission").unwrap();
    assert_eq!(
        planned,
        ids(&["other", "shared", "enemy", "weapon", "mission"])
    );
    assert_eq!(selected, ids(&["other"]));
    assert_eq!(plan_enable(&graph(), &planned, "mission").unwrap(), planned);
}
#[test]
fn unavailable_incompatible_api_cycles_and_conflicts_leave_selection_unchanged() {
    let initial = ids(&["other"]);
    let check = |graph: &Discovery, expected: &str| {
        let error = plan_enable(graph, &initial, "mission")
            .unwrap_err()
            .to_string();
        assert!(error.contains(expected), "{error}");
        assert_eq!(initial, ids(&["other"]));
    };
    let mut g = graph();
    g.mods.remove("shared");
    check(&g, "install it");
    let mut g = graph();
    g.mods.get_mut("shared").unwrap().manifest.version = "2.0.0".into();
    check(&g, "installed 2.0.0");
    let mut g = graph();
    g.mods.get_mut("shared").unwrap().manifest.api_version = 2;
    check(&g, "requires API 2");
    let mut g = graph();
    g.mods
        .get_mut("shared")
        .unwrap()
        .manifest
        .dependencies
        .insert("mission".into(), "^1".into());
    check(&g, "cyclic");
    let mut g = graph();
    g.mods
        .get_mut("other")
        .unwrap()
        .manifest
        .conflicts
        .push("weapon".into());
    check(&g, "conflicts");
}
#[test]
fn disable_plan_removes_transitive_dependents_but_preserves_unrelated_mods() {
    let initial = ids(&["other", "shared", "enemy", "weapon", "mission", "sequel"]);
    let plan = plan_disable(&graph(), &initial, "weapon");
    assert_eq!(
        plan.removed,
        ids(&["shared", "enemy", "weapon", "mission", "sequel"])
    );
    assert_eq!(plan.enabled, ids(&["other"]));
    // Merely opening the confirmation must not change the pending selection.
    assert_eq!(
        initial,
        ids(&["other", "shared", "enemy", "weapon", "mission", "sequel"])
    );
    assert_eq!(
        modding::order(&graph(), &plan.enabled).unwrap(),
        plan.enabled
    );
}
#[test]
fn disabling_a_shared_dependency_cascades_across_both_branches() {
    let initial = plan_enable(&graph(), &ids(&["other"]), "sequel").unwrap();
    let plan = plan_disable(&graph(), &initial, "shared");
    assert_eq!(plan.enabled, ids(&["other"]));
    assert_eq!(plan.removed.len(), 5);
    assert!(
        plan_disable(&graph(), &initial, "absent")
            .removed
            .is_empty()
    );
}
#[test]
fn disabling_a_missing_installed_package_can_still_remove_its_dependents() {
    let mut g = graph();
    g.mods.remove("shared");
    let initial = ids(&["shared", "weapon", "other"]);
    let plan = plan_disable(&g, &initial, "shared");
    assert_eq!(plan.removed, ids(&["shared", "weapon"]));
    assert_eq!(plan.enabled, ids(&["other"]));
}
#[test]
fn selecting_shipped_iron_coast_mission_selects_all_seven_real_dependencies() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("mods");
    let discovery = modding::discover(&root);
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let enabled = plan_enable(&discovery, &[], "iron_coast_mission_1").unwrap();
    assert_eq!(enabled.len(), 8);
    assert_eq!(enabled.last().unwrap(), "iron_coast_mission_1");
    for id in [
        "iron_coast_scout",
        "iron_coast_turret",
        "iron_coast_boss",
        "pulse_cannon",
        "seeker_swarm",
        "ion_lance",
        "iron_coast_music",
    ] {
        assert!(enabled.contains(&id.to_string()));
        let removal = plan_disable(&discovery, &enabled, id);
        assert_eq!(removal.removed, enabled);
        assert!(removal.enabled.is_empty());
    }
    assert_eq!(
        plan_disable(&discovery, &enabled, "iron_coast_mission_1").removed,
        enabled
    );
}

#[test]
fn another_remaining_campaign_preserves_the_shared_dependencies_it_needs() {
    let mut g = graph();
    g.mods.insert(
        "other_campaign".into(),
        package("other_campaign", &[("enemy", "^1")]),
    );
    let mut enabled = plan_enable(&g, &[], "mission").unwrap();
    enabled = plan_enable(&g, &enabled, "other_campaign").unwrap();
    let plan = plan_disable(&g, &enabled, "mission");
    assert_eq!(plan.removed, ids(&["weapon", "mission"]));
    assert_eq!(plan.enabled, ids(&["shared", "enemy", "other_campaign"]));
    assert_eq!(modding::order(&g, &plan.enabled).unwrap(), plan.enabled);
}

#[test]
fn a_standalone_mod_has_exactly_one_removal_for_the_instant_toggle() {
    let enabled = plan_enable(&graph(), &ids(&["other"]), "mission").unwrap();
    let plan = plan_disable(&graph(), &enabled, "other");
    assert_eq!(plan.removed, ids(&["other"]));
    assert_eq!(plan.enabled, ids(&["shared", "enemy", "weapon", "mission"]));
}
