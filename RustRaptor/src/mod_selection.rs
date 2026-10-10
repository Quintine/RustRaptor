//! Dependency-aware plans for the manager's pending selections.
//! Planning never changes active content, installed files or the caller's list.
use crate::{
    content::API_VERSION,
    modding::{self, Discovery},
};
use anyhow::{Context, Result, ensure};
use semver::{Version, VersionReq};
use std::collections::BTreeSet;

/// Check and select the requested package and its installed dependencies.
/// Existing independent priority is preserved; dependencies precede dependents.
pub fn plan_enable(discovery: &Discovery, enabled: &[String], id: &str) -> Result<Vec<String>> {
    let mut selected = enabled.to_vec();
    if !selected.iter().any(|value| value == id) {
        selected.push(id.into());
    }
    let roots = selected.clone();
    let mut visiting = BTreeSet::new();
    let mut done = BTreeSet::new();

    fn visit(
        discovery: &Discovery,
        id: &str,
        selected: &mut Vec<String>,
        visiting: &mut BTreeSet<String>,
        done: &mut BTreeSet<String>,
    ) -> Result<()> {
        if done.contains(id) {
            return Ok(());
        }
        ensure!(
            visiting.len() < 256,
            "dependency chain exceeds 256 packages at {id}"
        );
        ensure!(visiting.insert(id.into()), "cyclic mod dependency at {id}");
        let package = discovery
            .mods
            .get(id)
            .with_context(|| format!("mod {id} is not installed; install it, then rescan Mods"))?;
        ensure!(
            package.manifest.api_version == API_VERSION,
            "{id}: requires API {}, game provides {API_VERSION}",
            package.manifest.api_version
        );
        for (dependency, requirement) in &package.manifest.dependencies {
            let installed = discovery.mods.get(dependency).with_context(|| {
                format!("{id} requires {dependency} {requirement}; install it, then rescan Mods")
            })?;
            let version = Version::parse(&installed.manifest.version)
                .with_context(|| format!("{dependency}: invalid installed version"))?;
            ensure!(
                VersionReq::parse(requirement)?.matches(&version),
                "{id} requires {dependency} {requirement}, installed {version}"
            );
            if !selected.contains(dependency) {
                selected.push(dependency.clone());
            }
            visit(discovery, dependency, selected, visiting, done)?;
        }
        visiting.remove(id);
        done.insert(id.into());
        Ok(())
    }

    for root in roots {
        visit(discovery, &root, &mut selected, &mut visiting, &mut done)?;
    }
    // Reuse activation's API/conflict/version/order checks. Nothing is committed
    // if any selected package or newly discovered dependency fails validation.
    modding::order(discovery, &selected)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisablePlan {
    /// Pending selection after accepting this plan.
    pub enabled: Vec<String>,
    /// Requested package, dependents and unused dependencies, in current order.
    pub removed: Vec<String>,
}

/// Plan a removal with dependent packages and their now-unused dependencies.
/// Dependencies needed by another remaining package stay selected. The manager
/// confirms plans affecting multiple packages; a single package toggles directly.
pub fn plan_disable(discovery: &Discovery, enabled: &[String], id: &str) -> DisablePlan {
    let mut removed = BTreeSet::new();
    if enabled.iter().any(|value| value == id) {
        removed.insert(id.to_string());
    }
    loop {
        let before = removed.len();
        for candidate in enabled {
            if discovery.mods.get(candidate).is_some_and(|package| {
                package
                    .manifest
                    .dependencies
                    .keys()
                    .any(|dependency| removed.contains(dependency))
            }) {
                removed.insert(candidate.clone());
            }
        }
        if removed.len() == before {
            break;
        }
    }
    fn dependencies(discovery: &Discovery, roots: &BTreeSet<String>) -> BTreeSet<String> {
        let mut found = BTreeSet::new();
        let mut queue: Vec<_> = roots.iter().cloned().collect();
        while let Some(id) = queue.pop() {
            if let Some(package) = discovery.mods.get(&id) {
                for dependency in package.manifest.dependencies.keys() {
                    if found.insert(dependency.clone()) {
                        queue.push(dependency.clone());
                    }
                }
            }
        }
        found
    }
    let candidates = dependencies(discovery, &removed);
    let remaining_roots = enabled
        .iter()
        .filter(|id| !removed.contains(*id) && !candidates.contains(*id))
        .cloned()
        .collect();
    let still_needed = dependencies(discovery, &remaining_roots);
    let selected: BTreeSet<_> = enabled.iter().cloned().collect();
    removed.extend(
        candidates
            .into_iter()
            .filter(|id| selected.contains(id) && !still_needed.contains(id)),
    );
    DisablePlan {
        enabled: enabled
            .iter()
            .filter(|id| !removed.contains(*id))
            .cloned()
            .collect(),
        removed: enabled
            .iter()
            .filter(|id| removed.contains(*id))
            .cloned()
            .collect(),
    }
}
