//! Explicit existing-environment selection is read-only; packages are never installed here.
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};
use std::{fs, thread};

fn probe(mut command: Command) -> Option<Vec<u8>> {
    command
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command.spawn().ok()?;
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => {
                return child.wait_with_output().ok().map(|out| out.stdout)
            }
            Ok(Some(_)) => return None,
            Ok(None) if start.elapsed() < Duration::from_secs(8) => {
                thread::sleep(Duration::from_millis(40))
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
        }
    }
}

pub fn inspect(path: &Path) -> serde_json::Value {
    let name = path
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();
    let allowed = name == "python"
        || name == "python.exe"
        || name == "python3"
        || name == "python3.exe"
        || name.starts_with("python3.")
            && name.trim_end_matches(".exe")[8..]
                .chars()
                .all(|char| char.is_ascii_digit());
    let invalid = || serde_json::json!({"path": path, "version": null, "ready": false, "reason": "invalid", "missing": []});
    if !allowed
        || !path.is_absolute()
        || !path.is_file()
        || path.to_string_lossy().contains("WindowsApps")
    {
        return invalid();
    }
    let mut command = Command::new(path);
    command.args(["-I", "-c", "import sys,json,importlib.util; names=['uvicorn','fastapi','pydantic','httpx','aiosqlite','PIL','multipart','quickjs']; print(json.dumps({'version':'.'.join(map(str,sys.version_info[:3])),'supported':sys.version_info>=(3,10),'missing':[n for n in names if importlib.util.find_spec(n) is None]}))"])
        .env_remove("PYTHONHOME").env_remove("PYTHONPATH");
    let Some(bytes) = probe(command) else {
        return invalid();
    };
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(&bytes) else {
        return invalid();
    };
    let missing = value["missing"].as_array().cloned().unwrap_or_default();
    let supported = value["supported"].as_bool().unwrap_or(false);
    let ready = supported && missing.is_empty() && crate::bootstrap::runtime_usable(path);
    serde_json::json!({"path": path, "version": value["version"], "ready": ready,
        "reason": if ready { "ready" } else if !supported { "version" } else { "dependencies" }, "missing": missing})
}

pub fn discover(root: &Path) -> Vec<serde_json::Value> {
    let mut paths = vec![
        root.join("backend/.venv/Scripts/python.exe"),
        root.join("backend/.venv/bin/python"),
        root.join("runtime/python/python.exe"),
    ];
    if let Some(python) = crate::bootstrap::managed_python(root) {
        paths.push(python);
    }
    #[cfg(windows)]
    {
        let windows =
            PathBuf::from(std::env::var_os("SystemRoot").unwrap_or_else(|| "C:\\Windows".into()));
        let mut command = Command::new(windows.join("System32/where.exe"));
        command.args(["python", "python3"]);
        if let Some(output) = probe(command) {
            paths.extend(String::from_utf8_lossy(&output).lines().map(PathBuf::from));
        }
        let mut command = Command::new("py");
        command.arg("-0p");
        if let Some(output) = probe(command) {
            for line in String::from_utf8_lossy(&output).lines() {
                if let Some(colon) = line.find(":\\") {
                    if colon > 0 {
                        paths.push(PathBuf::from(line[colon - 1..].trim()));
                    }
                }
            }
        }
    }
    #[cfg(not(windows))]
    if let Some(path) = std::env::var_os("PATH") {
        for directory in std::env::split_paths(&path) {
            paths.push(directory.join("python3"));
        }
    }
    let mut seen = std::collections::HashSet::new();
    paths
        .into_iter()
        .filter_map(|path| path.canonicalize().ok())
        .filter(|path| seen.insert(path.to_string_lossy().to_lowercase()))
        .take(8)
        .map(|path| inspect(&path))
        .collect()
}

pub fn selected(root: &Path) -> Result<Option<PathBuf>, String> {
    let config = crate::bootstrap::runtime_dir(root).join("selected-python.json");
    if !config.exists() {
        return Ok(None);
    }
    let bytes = fs::read(config).map_err(|_| "Cannot read selected environment")?;
    let value: serde_json::Value = serde_json::from_slice(&bytes)
        .map_err(|_| "Selected environment configuration is invalid")?;
    let path = PathBuf::from(
        value["path"]
            .as_str()
            .ok_or("Selected environment path is missing")?,
    );
    if inspect(&path)["ready"] != true {
        return Err("Selected environment is unavailable or incomplete; choose another or prepare an isolated environment".into());
    }
    Ok(Some(path))
}

pub fn select(root: &Path, path: &Path) -> Result<(), String> {
    if inspect(path)["ready"] != true {
        return Err("Choose Python 3.10+ with the required Berry dependencies; system packages will not be modified".into());
    }
    let directory = crate::bootstrap::runtime_dir(root);
    crate::bootstrap::verify_storage_path(&directory)?;
    fs::create_dir_all(&directory).map_err(|_| "Cannot save environment selection")?;
    let temporary = directory.join(format!("selected-{}.tmp", std::process::id()));
    fs::write(
        &temporary,
        serde_json::to_vec(&serde_json::json!({"path": path})).unwrap(),
    )
    .map_err(|_| "Cannot save environment selection")?;
    fs::rename(temporary, directory.join("selected-python.json"))
        .map_err(|_| "Cannot save environment selection".into())
}

pub fn clear(root: &Path) -> Result<(), String> {
    let path = crate::bootstrap::runtime_dir(root).join("selected-python.json");
    crate::bootstrap::verify_storage_path(&path)?;
    if path.exists() {
        fs::remove_file(path).map_err(|_| "Cannot change the selected environment")?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn arbitrary_programs_and_relative_paths_are_not_python_environments() {
        assert_eq!(inspect(Path::new("python.exe"))["ready"], false);
        assert_eq!(
            inspect(Path::new("C:/Windows/System32/cmd.exe"))["reason"],
            "invalid"
        );
        assert!(select(Path::new("missing-root"), Path::new("python.exe")).is_err());
    }
}
