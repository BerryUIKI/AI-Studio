//! App-owned core runtime setup; no host Python installation or engine packages.
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};
use std::sync::{atomic::{AtomicBool, Ordering}, mpsc};
use std::io::{BufRead, BufReader};
use fs2::FileExt;

/// Install only after an explicit UI action; downloads are not inference calls.
pub fn install(root: &Path, cancel: &AtomicBool, progress: impl Fn(&str)) -> Result<(), String> {
    if !supported() { return Err("Automatic environment setup supports Windows x64 only".into()); }
    let directory = runtime_dir(root);
    verify_storage_path(&directory)?;
    std::fs::create_dir_all(&directory).map_err(|_| "Application runtime storage is not writable")?;
    let lock = std::fs::OpenOptions::new().create(true).truncate(false).read(true).write(true)
        .open(directory.join("setup.lock")).map_err(|_| "Cannot open setup lock")?;
    lock.try_lock_exclusive().map_err(|_| "Environment setup is already running in another Berry window")?;
    let script = directory.join("bootstrap.ps1");
    std::fs::write(&script, include_str!("bootstrap.ps1")).map_err(|_| "Cannot prepare environment setup")?;
    let shell = PathBuf::from(std::env::var_os("SystemRoot").unwrap_or_else(|| "C:\\Windows".into()))
        .join("System32/WindowsPowerShell/v1.0/powershell.exe");
    let mut command = Command::new(shell);
    command.args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(&script).arg("-SourceRoot").arg(root).arg("-DataRoot").arg(data_dir())
        .arg("-RuntimeDir").arg(&directory).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::null());
    let mut process = crate::setup_process::SetupProcess::spawn(&mut command)?;
    let stdout = process.child.stdout.take().ok_or("Cannot read setup status")?;
    let (send, receive) = mpsc::channel();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
                if let Some(stage) = value["stage"].as_str() { let _ = send.send(stage.to_owned()); }
            }
        }
    });
    let started = Instant::now();
    loop {
        if cancel.load(Ordering::SeqCst) { return Err("Environment setup cancelled".into()); }
        if started.elapsed() > Duration::from_secs(1200) { return Err("Environment setup timed out; retry when connected".into()); }
        if let Ok(stage) = receive.recv_timeout(Duration::from_millis(100)) {
            if ["downloading", "verifying", "installing", "validating"].contains(&stage.as_str()) { progress(&stage); }
        }
        if let Some(status) = process.child.try_wait().map_err(|_| "Cannot observe environment setup")? {
            if !status.success() { return Err("Environment setup failed. Check network access to GitHub and PyPI, then retry.".into()); }
            break;
        }
    }
    if !managed_python(root).is_some_and(|python| runtime_usable(&python)) {
        return Err("The created environment did not pass validation".into());
    }
    Ok(())
}

pub fn supported() -> bool {
    cfg!(all(windows, target_arch = "x86_64"))
}

pub(crate) fn verify_storage_path(path: &Path) -> Result<(), String> {
    for ancestor in path.ancestors() {
        if let Ok(metadata) = ancestor.symlink_metadata() {
            #[cfg(windows)]
            let redirected = { use std::os::windows::fs::MetadataExt; metadata.file_attributes() & 0x400 != 0 };
            #[cfg(not(windows))]
            let redirected = metadata.file_type().is_symlink();
            if redirected { return Err("Runtime storage must not redirect through links or junctions".into()); }
        }
    }
    Ok(())
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
