mod backend;

use std::sync::Mutex;
use std::process::Child;
use tauri::Manager;

pub struct AppState {
    pub backend_child: Mutex<Option<Child>>,
    pub port: u16,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = std::env::var("BERRY_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8000);

    let root_dir = backend::detect_root_dir();
    let child = backend::spawn_backend(&root_dir, port).ok().flatten();

    if !backend::wait_for_backend_ready(port, 15) {
        eprintln!("[Tauri] Warning: Berry backend failed to report ready within 15s");
    }

    let app_state = AppState {
        backend_child: Mutex::new(child),
        port,
    };

    tauri::Builder::default()
        .manage(app_state)
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // In production, navigate window directly to Berry core server
            if !cfg!(debug_assertions) {
                if let Some(main_window) = app.get_webview_window("main") {
                    let target_url = format!("http://127.0.0.1:{}", port);
                    if let Ok(url) = tauri::Url::parse(&target_url) {
                        let _ = main_window.navigate(url);
                    }
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<AppState>();
                let mut guard = state.backend_child.lock().unwrap();
                backend::shutdown_backend(state.port, guard.take());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
