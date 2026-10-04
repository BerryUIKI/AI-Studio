//! Berry AI Studio - Embedded Backend Supervisor for Tauri Desktop App
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, Instant};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

/// Write timestamped message to berry_desktop.log in the detected root directory.
pub fn log_msg(msg: &str) {
    let root = detect_root_dir();
    let log_file = root.join("berry_desktop.log");
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(log_file) {
        let _ = writeln!(f, "[{:.3?}] {}", Instant::now(), msg);
    }
}

/// Detect the workspace or repository root directory by walking all ancestors.
pub fn detect_root_dir() -> PathBuf {
    // 1. Check current_exe and ALL its ancestors
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors() {
            if ancestor.join("backend").join("app").join("main.py").is_file() {
                return ancestor.to_path_buf();
            }
        }
    }

    // 2. Check current_dir and ALL its ancestors
    if let Ok(cwd) = std::env::current_dir() {
        for ancestor in cwd.ancestors() {
            if ancestor.join("backend").join("app").join("main.py").is_file() {
                return ancestor.to_path_buf();
            }
        }
    }

    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// Locate Python executable (bundled hermetic runtime, local virtualenv, or system fallback).
pub fn find_python_executable(root_dir: &Path) -> Result<PathBuf, String> {
    let candidates = [
        root_dir.join("runtime").join("python").join("Scripts").join("python.exe"),
        root_dir.join("runtime").join("python").join("python.exe"),
        root_dir.join("runtime").join("python").join("bin").join("python"),
        root_dir.join("backend").join(".venv").join("Scripts").join("python.exe"),
        root_dir.join("backend").join(".venv").join("bin").join("python"),
    ];

    for candidate in &candidates {
        if candidate.is_file() {
            log_msg(&format!("Found python executable: {:?}", candidate));
            return Ok(candidate.clone());
        }
    }

    // System PATH fallback
    let sys_name = if cfg!(windows) { "python" } else { "python3" };
    if let Ok(output) = Command::new(sys_name).arg("--version").output() {
        if output.status.success() {
            log_msg(&format!("Using system PATH fallback python: {}", sys_name));
            return Ok(PathBuf::from(sys_name));
        }
    }

    let err = format!(
        "Python runtime not found in {:?}. Checked candidates: {:?}",
        root_dir, candidates
    );
    log_msg(&err);
    Err(err)
}

/// Check if Berry backend is responding on port.
pub fn is_backend_healthy(port: u16) -> bool {
    use std::net::{SocketAddr, TcpStream};
    let addr: SocketAddr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    // Fast fail if nothing is listening on TCP port
    if TcpStream::connect_timeout(&addr, Duration::from_millis(100)).is_err() {
        return false;
    }

    let url = format!("http://127.0.0.1:{}/health", port);
    let agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_millis(1000)))
        .build()
        .new_agent();

    match agent.get(&url).call() {
        Ok(mut resp) => {
            if resp.status().is_success() {
                if let Ok(body) = resp.body_mut().read_to_string() {
                    return body.contains("ai-workflow-backend") || body.contains("Berry AI Studio");
                }
            }
            false
        }
        Err(_) => false,
    }
}

/// Spawn the Berry backend core process if not already running.
pub fn spawn_backend(root_dir: &Path, port: u16) -> Result<Option<Child>, String> {
    if is_backend_healthy(port) {
        log_msg(&format!("Berry backend already running on port {}", port));
        return Ok(None);
    }

    let python_exe = find_python_executable(root_dir)?;
    let backend_dir = root_dir.join("backend");

    log_msg(&format!(
        "Spawning Berry core backend via {:?} in {:?}",
        python_exe, backend_dir
    ));

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

    let child = cmd.spawn().map_err(|e| {
        let err = format!("Failed to spawn backend process: {}", e);
        log_msg(&err);
        err
    })?;

    log_msg(&format!("Backend process spawned with PID {}", child.id()));
    Ok(Some(child))
}

/// Poll backend health until ready or timeout.
pub fn wait_for_backend_ready(port: u16, timeout_secs: u64, child: &mut Option<Child>) -> bool {
    let start = Instant::now();
    let timeout = Duration::from_secs(timeout_secs);
    while start.elapsed() < timeout {
        // Check if child exited prematurely
        if let Some(proc) = child.as_mut() {
            if let Ok(Some(status)) = proc.try_wait() {
                log_msg(&format!("Backend child exited prematurely with status: {}", status));
                return false;
            }
        }

        if is_backend_healthy(port) {
            log_msg(&format!("Backend is ready (elapsed: {:.2?})", start.elapsed()));
            return true;
        }
        thread::sleep(Duration::from_millis(300));
    }

    log_msg(&format!("Backend timed out after {}s", timeout_secs));
    false
}

/// Shutdown mode indicating the desired exit behavior.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShutdownMode {
    /// Keep running: do not terminate the backend or owned engines, leave background processes alive.
    KeepRunning,
    /// Stop owned: gracefully stop the owned backend and managed engines. Respects refusals unless forced.
    StopOwned { force: bool, stop_managed_engines: Option<bool> },
}

/// Result of a shutdown attempt.
#[derive(Debug, PartialEq, Eq)]
pub enum ShutdownResult {
    /// Backend shutdown acknowledged or not needed.
    Completed,
    /// Backend refused shutdown due to active tasks (HTTP 409). Child is NOT killed.
    RefusedActiveTasks,
    /// Backend was unowned (spawn_backend returned None), so no shutdown was sent.
    UnownedIgnored,
}

/// Gracefully shut down backend respecting process ownership and active tasks.
/// If `mode` is `KeepRunning`, or if `child` is `None` (unowned backend),
/// no shutdown request is sent and no process is killed.
/// If shutdown request returns 409 (Conflict - active tasks), the refusal is respected
/// and the child is NOT killed.
pub fn shutdown_backend(
    port: u16,
    mut child: Option<Child>,
    mode: ShutdownMode,
) -> (ShutdownResult, Option<Child>) {
    match mode {
        ShutdownMode::KeepRunning => {
            log_msg("ShutdownMode::KeepRunning requested: preserving backend and child process.");
            (ShutdownResult::Completed, child)
        }
        ShutdownMode::StopOwned { force, stop_managed_engines } => {
            if child.is_none() {
                log_msg("No owned child backend process found. Skipping shutdown request to preserve unowned/pre-existing backend.");
                return (ShutdownResult::UnownedIgnored, None);
            }

            let url = format!("http://127.0.0.1:{}/api/v1/manager/shutdown", port);
            log_msg(&format!(
                "Requesting graceful backend shutdown (force={}, stop_managed_engines={:?})...",
                force, stop_managed_engines
            ));

            let agent = ureq::Agent::config_builder()
                .timeout_global(Some(Duration::from_secs(3)))
                .build()
                .new_agent();

            let payload = serde_json::json!({
                "force": force,
                "stop_managed_engines": stop_managed_engines
            });

            let resp = agent.post(&url).send_json(payload);
            match resp {
                Ok(res) => {
                    log_msg(&format!("Backend shutdown acknowledged with status: {}", res.status()));
                    // Wait up to 3 seconds for graceful process exit
                    if let Some(mut proc) = child.take() {
                        let start = Instant::now();
                        let mut exited = false;
                        while start.elapsed() < Duration::from_secs(3) {
                            if let Ok(Some(status)) = proc.try_wait() {
                                log_msg(&format!("Backend child exited gracefully with status: {}", status));
                                exited = true;
                                break;
                            }
                            thread::sleep(Duration::from_millis(100));
                        }
                        if !exited && force {
                            log_msg("Force flag set and graceful wait exceeded. Terminating child.");
                            let _ = proc.kill();
                        } else if !exited {
                            log_msg("Child has not exited yet after acknowledgement. Allowing exit without SIGKILL.");
                        }
                    }
                    (ShutdownResult::Completed, None)
                }
                Err(ureq::Error::StatusCode(409)) => {
                    log_msg("Backend refused shutdown: active generation or workflow tasks are currently running (HTTP 409). Preserving child process.");
                    (ShutdownResult::RefusedActiveTasks, child)
                }
                Err(e) => {
                    log_msg(&format!("Backend shutdown request failed or unhandled: {}", e));
                    if force {
                        if let Some(mut proc) = child.take() {
                            log_msg("Force shutdown flag set; terminating child process.");
                            let _ = proc.kill();
                        }
                        (ShutdownResult::Completed, None)
                    } else {
                        log_msg("Non-forced shutdown failed to communicate safely. Preserving child process.");
                        (ShutdownResult::RefusedActiveTasks, child)
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shutdown_keep_running_preserves_backend() {
        // Mode KeepRunning must return Completed without sending any network request
        // and without killing or dropping the child process handle
        let (res, child) = shutdown_backend(8000, None, ShutdownMode::KeepRunning);
        assert_eq!(res, ShutdownResult::Completed);
        assert!(child.is_none());
    }

    #[test]
    fn test_shutdown_unowned_backend_ignored() {
        // If child is None (unowned / pre-existing backend), StopOwned must NOT send a shutdown request
        // and must return UnownedIgnored
        let (res, child) = shutdown_backend(
            8000,
            None,
            ShutdownMode::StopOwned {
                force: false,
                stop_managed_engines: None,
            },
        );
        assert_eq!(res, ShutdownResult::UnownedIgnored);
        assert!(child.is_none());
    }
}

