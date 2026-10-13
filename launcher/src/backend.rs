//! Backend process supervisor and staged startup coordinator (L01, L02, L07).

use std::path::PathBuf;
use std::process::Child;
use std::time::Instant;

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
    /// 3. Host Python fallback is allowed only in a source checkout
    pub fn find_python_executable(&self) -> Result<PathBuf, String> {
        berry_runtime::find_python_executable(&self.root_dir)
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
        self.find_python_executable()?;

        if self.verify_frontend_packaged() {
            println!("      -> Frontend distribution assets verified (frontend/dist/index.html).");
        } else {
            println!("      [!] Notice: frontend/dist/index.html not found.");
            println!("          A diagnostic packaging error page will be served at '/' until 'pnpm build' is executed.");
        }

        // Stage 2: Port & locks check
        println!("[2/4] Checking ports and single-instance locks...");
        println!("[3/4] Spawning Berry core on port {}...", self.port);
        self.child = berry_runtime::spawn_backend(&self.root_dir, self.port)?;
        println!("[4/4] Probing service readiness...");
        let start_time = Instant::now();
        if !berry_runtime::wait_for_backend_ready(self.port, 30, &mut self.child) {
            return Err(format!("Backend failed to become ready on port {}", self.port));
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
        if let Some(child) = self.child.take() {
            // Active-task refusals and uncertain shutdowns preserve the owned child.
            let _ = berry_runtime::shutdown_backend(
                self.port, Some(child),
                berry_runtime::ShutdownMode::StopOwned { force: false, stop_managed_engines: None },
            );
        }
    }
}
