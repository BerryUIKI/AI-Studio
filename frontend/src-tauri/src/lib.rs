mod backend;
mod startup;

use std::process::Child;
use std::sync::Mutex;
use tauri::Manager;

pub struct AppState {
    pub backend_child: Mutex<Option<Child>>,
    pub port: u16,
    pub root_dir: std::path::PathBuf,
    pub startup: Mutex<startup::StartupStatus>,
    pub setup_running: std::sync::atomic::AtomicBool,
    pub setup_cancel: std::sync::atomic::AtomicBool,
}

#[derive(serde::Deserialize)]
pub struct CloseAppPayload {
    pub mode: Option<String>, // "keep_running" | "stop_owned"
    pub force: Option<bool>,
    pub stop_managed_engines: Option<bool>,
}

#[derive(serde::Serialize)]
pub struct CloseAppResult {
    pub success: bool,
    pub refused: bool,
    pub message: String,
}

#[tauri::command]
fn close_app(
    app_handle: tauri::AppHandle,
    window: tauri::Window,
    payload: Option<CloseAppPayload>,
) -> CloseAppResult {
    let state = app_handle.state::<AppState>();
    state
        .setup_cancel
        .store(true, std::sync::atomic::Ordering::SeqCst);
    let mode_str = payload
        .as_ref()
        .and_then(|p| p.mode.as_deref())
        .unwrap_or("stop_owned");
    let force = payload.as_ref().and_then(|p| p.force).unwrap_or(false);
    let stop_engines = payload.as_ref().and_then(|p| p.stop_managed_engines);

    let shutdown_mode = if mode_str == "keep_running" {
        backend::ShutdownMode::KeepRunning
    } else {
        backend::ShutdownMode::StopOwned {
            force,
            stop_managed_engines: stop_engines,
        }
    };

    let mut guard = state.backend_child.lock().unwrap();
    let child = guard.take();
    let (res, preserved_child) = backend::shutdown_backend(state.port, child, shutdown_mode);

    match res {
        backend::ShutdownResult::RefusedActiveTasks => {
            // Restore child back into AppState
            *guard = preserved_child;
            CloseAppResult {
                success: false,
                refused: true,
                message: "Shutdown refused: active generation tasks are running.".to_string(),
            }
        }
        backend::ShutdownResult::Completed => {
            // If keep_running, child is preserved in background or consumed
            *guard = preserved_child;
            let _ = window.destroy();
            app_handle.exit(0);
            CloseAppResult {
                success: true,
                refused: false,
                message: "Application closed successfully.".to_string(),
            }
        }
        backend::ShutdownResult::UnownedIgnored => {
            *guard = None;
            let _ = window.destroy();
            app_handle.exit(0);
            CloseAppResult {
                success: true,
                refused: false,
                message: "Unowned backend preserved, window closed.".to_string(),
            }
        }
    }
}

#[tauri::command]
fn minimize_app(window: tauri::Window) {
    let _ = window.minimize();
}

/// Resolve the package root, preferring the Tauri resource directory of an installed build.
///
/// The NSIS installer ships the backend and runtime as Tauri resources next to the
/// executable. Development and portable layouts keep them beside the binary instead, so
/// the resource directory is only used when it actually contains the backend.
fn resolve_root_dir() -> std::path::PathBuf {
    let resource_dir = std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|dir| dir.join("resources")));
    berry_runtime::detect_root_dir_with(resource_dir.as_deref())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    backend::log_msg("=== Berry AI Studio Starting ===");
    let port = std::env::var("BERRY_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8000);

    let root_dir = resolve_root_dir();
    backend::log_msg(&format!("Detected root directory: {:?}", root_dir));

    let mut child = match backend::spawn_backend(&root_dir, port) {
        Ok(c) => c,
        Err(e) => {
            backend::log_msg(&format!("Error spawning backend: {}", e));
            None
        }
    };

    let is_ready = (child.is_some() || berry_runtime::is_backend_healthy(port))
        && backend::wait_for_backend_ready(port, 30, &mut child);
    let app_state = AppState {
        backend_child: Mutex::new(child),
        port,
        startup: Mutex::new(startup::StartupStatus {
            phase: if is_ready {
                "ready"
            } else {
                "needs_environment"
            }
            .into(),
            details: String::new(),
            environment_path: berry_runtime::bootstrap::runtime_dir(&root_dir)
                .display()
                .to_string(),
            can_install: berry_runtime::bootstrap::supported(),
            error_code: String::new(),
            volume: String::new(),
            available_bytes: None,
            required_bytes: None,
            downloaded_bytes: None,
            total_bytes: None,
        }),
        root_dir,
        setup_running: std::sync::atomic::AtomicBool::new(false),
        setup_cancel: std::sync::atomic::AtomicBool::new(false),
    };
    tauri::Builder::default()
        .manage(app_state)
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            close_app,
            minimize_app,
            startup::startup_status,
            startup::discover_environments,
            startup::inspect_environment,
            startup::prepare_environment,
            startup::cancel_environment_setup
        ])
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            if is_ready {
                if let Some(window) = app.get_webview_window("main") {
                    window.navigate(tauri::Url::parse(&format!("http://127.0.0.1:{}", port))?)?;
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<AppState>();
                state
                    .setup_cancel
                    .store(true, std::sync::atomic::Ordering::SeqCst);
                let mut guard = state.backend_child.lock().unwrap();
                let child = guard.take();
                // When window is destroyed directly (e.g. OS kill / Alt+F4), stop owned child cleanly
                let (_, remaining) = backend::shutdown_backend(
                    state.port,
                    child,
                    backend::ShutdownMode::StopOwned {
                        force: false,
                        stop_managed_engines: None,
                    },
                );
                *guard = remaining;
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
