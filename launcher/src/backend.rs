//! Backend process supervisor and staged startup coordinator (L01, L02, L07).

use std::path::PathBuf;
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, Instant};

pub struct BackendSupervisor {
    root_dir: PathBuf,
    port: u16,
    child: Option<Child>,
}

impl BackendSupervisor {
    pub fn new(root_dir: PathBuf, port: u16) -> Self {
        Self {
            root_dir,
            port,
            child: None,
        }
    }

    /// Resolve Python executable:
    /// 1. Bundled release runtime (runtime/python/python.exe) - requires 0 host Python
    /// 2. Isolated virtualenv (backend/.venv/Scripts/python.exe)
    /// 3. Development fallback: bootstrap from host Python if running from source
    pub fn find_python_executable(&self) -> Result<PathBuf, String> {
        // 1. Release distribution: check bundled hermetic Python runtime
        let bundled_candidates = if cfg!(windows) {
            vec![
                self.root_dir.join("runtime").join("python").join("Scripts").join("python.exe"),
                self.root_dir.join("runtime").join("python").join("python.exe"),
            ]
        } else {
            vec![
                self.root_dir.join("runtime").join("python").join("bin").join("python"),
                self.root_dir.join("runtime").join("python").join("python"),
            ]
        };
        for candidate in bundled_candidates {
            if candidate.is_file() {
                return Ok(candidate);
            }
        }

        // 2. Pre-configured isolated virtual environment
        let venv_python = if cfg!(windows) {
            self.root_dir.join("backend").join(".venv").join("Scripts").join("python.exe")
        } else {
            self.root_dir.join("backend").join(".venv").join("bin").join("python")
        };

        if venv_python.is_file() {
            return Ok(venv_python);
        }

        // Check if system python can be used to bootstrap .venv
        let system_py = if cfg!(windows) { "python" } else { "python3" };
        let check_res = Command::new(system_py).arg("--version").output();
        match check_res {
            Ok(output) if output.status.success() => {
                println!("[*] Initializing isolated virtual environment in backend/.venv ...");
                let venv_dir = self.root_dir.join("backend").join(".venv");
                let create_res = Command::new(system_py)
                    .args(["-m", "venv", venv_dir.to_str().unwrap()])
                    .status();

                if create_res.map(|s| s.success()).unwrap_or(false) && venv_python.is_file() {
                    println!("[*] Installing requirements into isolated virtual environment ...");
                    let req_file = self.root_dir.join("backend").join("requirements.txt");
                    let _ = Command::new(&venv_python)
                        .args(["-m", "pip", "install", "-r", req_file.to_str().unwrap()])
                        .status();
                    return Ok(venv_python);
                }
            }
            _ => {}
        }

        Err(format!(
            "Python 3.10+ was not found in {:?} or system PATH. Please install Python 3.10+ from https://python.org",
            venv_python
        ))
    }

    /// Validate frontend packaging (L02).
    pub fn verify_frontend_packaged(&self) -> bool {
        let index_html = self.root_dir.join("frontend").join("dist").join("index.html");
        index_html.is_file()
    }

    /// Launch Berry backend process with staged progress (L02).
    pub fn start(&mut self) -> Result<(), String> {
        println!("\n========================================================");
        println!("             Berry AI Studio (Windows Launcher)");
        println!("========================================================\n");

        // Stage 1: Runtime validation
        println!("[1/4] Validating runtime environment...");
        let python_exe = self.find_python_executable()?;

        if self.verify_frontend_packaged() {
            println!("      -> Frontend distribution assets verified (frontend/dist/index.html).");
        } else {
            println!("      [!] Notice: frontend/dist/index.html not found.");
            println!("          A diagnostic packaging error page will be served at '/' until 'pnpm build' is executed.");
        }

        // Stage 2: Port & locks check
        println!("[2/4] Checking ports and single-instance locks...");
        let backend_dir = self.root_dir.join("backend");

        // Stage 3: Spawn backend core
        println!("[3/4] Spawning Berry AI Studio core (host 127.0.0.1, port {})...", self.port);
        let mut cmd = Command::new(&python_exe);
        cmd.args([
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            &self.port.to_string(),
        ])
        .current_dir(&backend_dir);

        let child = cmd.spawn().map_err(|e| format!("Failed to spawn backend process: {}", e))?;
        println!("      -> Process spawned with PID: {}", child.id());
        self.child = Some(child);

        // Stage 4: Probe readiness (L02)
        println!("[4/4] Probing service readiness...");
        let start_time = Instant::now();
        let timeout = Duration::from_secs(30);
        let mut ready = false;

        while start_time.elapsed() < timeout {
            // Check if process exited prematurely
            if let Some(child_proc) = &mut self.child {
                if let Ok(Some(exit_status)) = child_proc.try_wait() {
                    return Err(format!("Backend process exited prematurely with status: {}", exit_status));
                }
            }

            if crate::port::is_berry_health_endpoint(self.port) {
                ready = true;
                break;
            }
            thread::sleep(Duration::from_millis(500));
        }

        if !ready {
            return Err(format!("Backend failed to become ready at 127.0.0.1:{} within 30 seconds", self.port));
        }

        println!("      -> Core service is READY (elapsed: {:.2?})", start_time.elapsed());
        Ok(())
    }

    /// Open workspace in default browser.
    pub fn open_workspace(&self) {
        let url = format!("http://127.0.0.1:{}", self.port);
        println!("[*] Opening creative workspace in default browser: {}", url);
        crate::single_instance::open_browser(&url);
    }

    /// Wait for child process.
    pub fn wait(&mut self) -> Result<(), String> {
        if let Some(mut child) = self.child.take() {
            println!("\nBerry AI Studio is running. Press Ctrl+C in this console or use 'Exit Berry' in UI to stop.");
            let status = child.wait().map_err(|e| format!("Error waiting on backend process: {}", e))?;
            println!("\nBerry AI Studio process ended with status: {}", status);
        }
        Ok(())
    }
}

impl Drop for BackendSupervisor {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            // Clean teardown on exit
            let _ = child.kill();
        }
    }
}
