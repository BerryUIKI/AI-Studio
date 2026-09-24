//! Berry AI Studio - Embedded Backend Supervisor for Tauri Desktop App
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, Instant};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

/// Detect the workspace or repository root directory.
pub fn detect_root_dir() -> PathBuf {
    // 1. Check current working directory
    if let Ok(cwd) = std::env::current_dir() {
        if cwd.join("backend").join("app").join("main.py").is_file() {
            return cwd;
        }
        if let Some(parent) = cwd.parent() {
            if parent.join("backend").join("app").join("main.py").is_file() {
                return parent.to_path_buf();
            }
        }
    }

    // 2. Check executable directory and ancestor paths
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            if exe_dir.join("backend").join("app").join("main.py").is_file() {
                return exe_dir.to_path_buf();
            }
            if let Some(p1) = exe_dir.parent() {
                if p1.join("backend").join("app").join("main.py").is_file() {
                    return p1.to_path_buf();
                }
                if let Some(p2) = p1.parent() {
                    if p2.join("backend").join("app").join("main.py").is_file() {
                        return p2.to_path_buf();
                    }
                    if let Some(p3) = p2.parent() {
                        if p3.join("backend").join("app").join("main.py").is_file() {
                            return p3.to_path_buf();
                        }
                    }
                }
            }
        }
    }

    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// Locate Python executable (bundled hermetic runtime, local virtualenv, or system fallback).
pub fn find_python_executable(root_dir: &Path) -> Result<PathBuf, String> {
    // 1. Release distribution: check bundled hermetic Python runtime
    let bundled = if cfg!(windows) {
        root_dir.join("runtime").join("python").join("python.exe")
    } else {
        root_dir.join("runtime").join("python").join("bin").join("python")
    };
    if bundled.is_file() {
        return Ok(bundled);
    }

    // 2. Local development virtual environment
    let venv_py = if cfg!(windows) {
        root_dir.join("backend").join(".venv").join("Scripts").join("python.exe")
    } else {
        root_dir.join("backend").join(".venv").join("bin").join("python")
    };
    if venv_py.is_file() {
        return Ok(venv_py);
    }

    // 3. System PATH fallback
    let sys_name = if cfg!(windows) { "python" } else { "python3" };
    if let Ok(output) = Command::new(sys_name).arg("--version").output() {
        if output.status.success() {
            return Ok(PathBuf::from(sys_name));
        }
    }

    Err(format!(
        "Python runtime not found. Checked: {:?} and {:?}",
        bundled, venv_py
    ))
}

/// Check if Berry backend is responding on port.
pub fn is_backend_healthy(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{}/health", port);
    let agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_millis(400)))
        .build()
        .new_agent();
    agent.get(&url)
        .call()
        .map(|r| r.status() == 200)
        .unwrap_or(false)
}

/// Spawn the Berry backend core process if not already running.
pub fn spawn_backend(root_dir: &Path, port: u16) -> Result<Option<Child>, String> {
    if is_backend_healthy(port) {
        println!("[Tauri] Berry backend already running on port {}", port);
        return Ok(None);
    }

    let python_exe = find_python_executable(root_dir)?;
    let backend_dir = root_dir.join("backend");

    println!("[Tauri] Spawning Berry core backend via {:?}", python_exe);
    let mut cmd = Command::new(&python_exe);
    cmd.args([
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        &port.to_string(),
    ])
    .current_dir(&backend_dir);

    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    let child = cmd.spawn().map_err(|e| format!("Failed to spawn backend process: {}", e))?;
    println!("[Tauri] Backend process spawned with PID {}", child.id());
    Ok(Some(child))
}

/// Poll backend health until ready or timeout.
pub fn wait_for_backend_ready(port: u16, timeout_secs: u64) -> bool {
    let start = Instant::now();
    let timeout = Duration::from_secs(timeout_secs);
    while start.elapsed() < timeout {
        if is_backend_healthy(port) {
            return true;
        }
        thread::sleep(Duration::from_millis(200));
    }
    false
}

/// Gracefully shut down backend.
pub fn shutdown_backend(port: u16, mut child: Option<Child>) {
    let url = format!("http://127.0.0.1:{}/api/v1/manager/shutdown", port);
    println!("[Tauri] Requesting graceful backend shutdown...");
    let agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(2)))
        .build()
        .new_agent();
    let _ = agent.post(&url)
        .send_json(serde_json::json!({ "force": false }));

    if let Some(mut proc) = child.take() {
        thread::sleep(Duration::from_millis(500));
        let _ = proc.kill();
    }
}
