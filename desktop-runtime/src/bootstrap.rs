//! App-owned core runtime setup; no host Python installation or engine packages.
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

pub fn supported() -> bool {
    cfg!(all(windows, target_arch = "x86_64"))
}

pub fn data_dir() -> PathBuf {
    if let Some(value) = std::env::var_os("BERRY_DATA_DIR").or_else(|| std::env::var_os("AI_WORKFLOW_DATA_DIR")) {
        return PathBuf::from(value);
    }
    if cfg!(windows) {
        let local = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_else(std::env::temp_dir);
        local.join("BerryAIStudio")
    } else {
        PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".berry-ai")
    }
}

pub fn runtime_dir(root: &Path) -> PathBuf {
    let root = root.canonicalize().unwrap_or_else(|_| root.to_path_buf());
    let identity = format!("{:x}", Sha256::digest(root.to_string_lossy().as_bytes()));
    data_dir().join("runtime").join("core").join(&identity[..16])
}

pub fn managed_python(root: &Path) -> Option<PathBuf> {
    let directory = runtime_dir(root).join("python");
    let marker = std::fs::read(directory.join("berry-core-ready.json")).ok()?;
    let marker: serde_json::Value = serde_json::from_slice(&marker).ok()?;
    let requirements = std::fs::read(root.join("backend/requirements.txt")).ok()?;
    let digest = format!("{:x}", Sha256::digest(requirements));
    if marker["requirements_sha256"] != digest { return None; }
    let python = directory.join(if cfg!(windows) { "python.exe" } else { "bin/python3" });
    python.is_file().then_some(python)
}

pub fn runtime_usable(python: &Path) -> bool {
    let mut command = Command::new(python);
    command.args(["-I", "-c", "import sys; assert sys.version_info >= (3,10); import uvicorn,fastapi,pydantic,httpx,aiosqlite,PIL,multipart,quickjs"])
        .env_remove("PYTHONHOME").env_remove("PYTHONPATH").stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    #[cfg(windows)]
    { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
    let Ok(mut child) = command.spawn() else { return false; };
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return status.success(),
            Ok(None) if started.elapsed() < Duration::from_secs(15) => thread::sleep(Duration::from_millis(50)),
            _ => { let _ = child.kill(); let _ = child.wait(); return false; }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn runtime_storage_is_owned_and_separate_per_installation() {
        let one = runtime_dir(Path::new("source-one"));
        let two = runtime_dir(Path::new("source-two"));
        assert!(one.starts_with(data_dir().join("runtime/core")));
        assert_ne!(one, two);
        assert_eq!(one, runtime_dir(Path::new("source-one")));
        assert!(managed_python(Path::new("missing-source")).is_none());
    }

    #[test]
    fn invalid_interpreter_is_not_ready() {
        assert!(!runtime_usable(Path::new("missing-python-executable")));
    }
}
