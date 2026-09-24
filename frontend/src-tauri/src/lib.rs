mod backend;

use std::sync::Mutex;
use std::process::Child;
use tauri::Manager;

pub struct AppState {
    pub backend_child: Mutex<Option<Child>>,
    pub port: u16,
    pub is_ready: bool,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    backend::log_msg("=== Berry AI Studio Starting ===");
    let port = std::env::var("BERRY_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8000);

    let root_dir = backend::detect_root_dir();
    backend::log_msg(&format!("Detected root directory: {:?}", root_dir));

    let mut child = match backend::spawn_backend(&root_dir, port) {
        Ok(c) => c,
        Err(e) => {
            backend::log_msg(&format!("Error spawning backend: {}", e));
            None
        }
    };

    let is_ready = backend::wait_for_backend_ready(port, 30, &mut child);

    let app_state = AppState {
        backend_child: Mutex::new(child),
        port,
        is_ready,
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

            if let Some(main_window) = app.get_webview_window("main") {
                if is_ready {
                    let target_url = format!("http://127.0.0.1:{}", port);
                    if let Ok(url) = tauri::Url::parse(&target_url) {
                        let _ = main_window.navigate(url);
                    }
                } else {
                    let error_html = format!(
                        r#"<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Berry AI Studio - Diagnostics</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; max-width: 600px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h1 {{ color: #f43f5e; font-size: 20px; margin-top: 0; }}
        p {{ line-height: 1.6; color: #cbd5e1; font-size: 14px; }}
        code {{ background: #0f172a; padding: 3px 8px; border-radius: 6px; font-family: Consolas, monospace; color: #38bdf8; }}
        .btn {{ display: inline-block; background: #2563eb; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 500; cursor: pointer; margin-top: 16px; border: none; }}
        .btn:hover {{ background: #1d4ed8; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Berry Core Backend Did Not Start</h1>
        <p>The Berry AI Studio core service on port <code>127.0.0.1:{}</code> did not become ready within 30s.</p>
        <p>Please check <code>berry_desktop.log</code> in the workspace directory for details.</p>
        <button class="btn" onclick="location.reload()">Retry Connection</button>
    </div>
</body>
</html>"#,
                        port
                    );
                    let _ = main_window.eval(&format!("document.write(`{}`); document.close();", error_html.replace('`', "\\`")));
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
