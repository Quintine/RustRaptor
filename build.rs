fn main() {
    println!("cargo:rerun-if-env-changed=HOME");
    if let Ok(home) = std::env::var("HOME") {
        let local = std::path::Path::new(&home).join(".local/lib");
        if local.join("libSDL2.so").exists() {
            println!("cargo:rustc-link-search=native={}", local.display());
        }
    }
}
