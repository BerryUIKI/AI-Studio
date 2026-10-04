mod backend;

use std::sync::Mutex;
use std::process::Child;
use tauri::Manager;

pub struct AppState {
    pub backend_child: Mutex<Option<Child>>,
    pub port: u16,
    pub is_ready: bool,
}

#[tauri::command]
fn close_app(app_handle: tauri::AppHandle, window: tauri::Window) {
    let state = app_handle.state::<AppState>();
    if let Ok(mut guard) = state.backend_child.lock() {
        backend::shutdown_backend(state.port, guard.take());
    }
    let _ = window.destroy();
    app_handle.exit(0);
}

#[tauri::command]
fn minimize_app(window: tauri::Window) {
    let _ = window.minimize();
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
        .invoke_handler(tauri::generate_handler![close_app, minimize_app])
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
                    let python_missing = backend::find_python_executable(&root_dir).is_err();
                    let diag_title = if python_missing {
                        "Python Environment Required / 需要 Python 环境"
                    } else {
                        "Berry Core Backend Did Not Start"
                    };
                    let diag_desc = if python_missing {
                        r#"未检测到可用的隔离 Python 运行环境（Python 3.10+）。<br/><span style="color:#94a3b8; font-size:13px;">No isolated Python runtime detected. Berry AI Studio uses an isolated environment to guarantee zero host pollution.</span>"#
                    } else {
                        r#"Berry AI Studio 后端服务未能及时就绪，请检查日志。<br/><span style="color:#94a3b8; font-size:13px;">The Berry AI Studio core service did not start within 30s.</span>"#
                    };

                    let error_html = format!(
                        r#"<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Berry AI Studio - Diagnostics</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; background: #0f172a; color: #f8fafc; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
        .titlebar {{ height: 44px; background: rgba(15, 23, 42, 0.95); border-bottom: 1px solid rgba(255, 255, 255, 0.08); display: flex; align-items: center; justify-content: space-between; padding: 0 12px; -webkit-app-region: drag; user-select: none; z-index: 100; }}
        .titlebar-brand {{ display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #e2e8f0; }}
        .titlebar-brand .logo {{ width: 22px; height: 22px; border-radius: 6px; background: linear-gradient(135deg, #6366f1, #a855f7); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; color: #fff; }}
        .titlebar-controls {{ display: flex; align-items: center; -webkit-app-region: no-drag; }}
        .t-btn {{ width: 36px; height: 32px; display: flex; align-items: center; justify-content: center; border: none; background: transparent; color: #94a3b8; cursor: pointer; border-radius: 4px; transition: all 0.15s; }}
        .t-btn:hover {{ background: rgba(255,255,255,0.08); color: #f8fafc; }}
        .t-btn.close:hover {{ background: #e11d48; color: #fff; }}
        .main-content {{ flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px; overflow-y: auto; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; max-width: 640px; width: 100%; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }}
        h1 {{ color: #f43f5e; font-size: 20px; margin-top: 0; display: flex; align-items: center; gap: 10px; }}
        p {{ line-height: 1.6; color: #cbd5e1; font-size: 14px; margin: 10px 0; }}
        .guide-box {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin: 16px 0; font-size: 13px; }}
        .guide-title {{ font-weight: 600; color: #38bdf8; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }}
        code {{ background: #1e293b; padding: 3px 8px; border-radius: 4px; font-family: Consolas, monospace; color: #38bdf8; font-size: 12px; }}
        pre {{ background: #0f172a; border: 1px solid #334155; padding: 10px 12px; border-radius: 6px; font-family: Consolas, monospace; color: #a5f3fc; font-size: 12px; overflow-x: auto; margin: 8px 0; }}
        .actions {{ display: flex; gap: 12px; margin-top: 20px; }}
        .btn {{ display: inline-flex; align-items: center; justify-content: center; background: #6366f1; color: #fff; padding: 9px 18px; border-radius: 8px; text-decoration: none; font-weight: 500; font-size: 13px; cursor: pointer; border: none; transition: background 0.15s; }}
        .btn:hover {{ background: #4f46e5; }}
        .btn.btn-secondary {{ background: #334155; color: #e2e8f0; }}
        .btn.btn-secondary:hover {{ background: #475569; }}
    </style>
</head>
<body>
    <div class="titlebar" data-tauri-drag-region>
        <div class="titlebar-brand">
            <div class="logo">B</div>
            <span>Berry AI Studio</span>
        </div>
        <div class="titlebar-controls">
            <button class="t-btn" title="Minimize" onclick="minimizeApp()">
                <svg width="12" height="12" viewBox="0 0 12 12"><line x1="1" y1="6" x2="11" y2="6" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
            <button class="t-btn close" title="Close" onclick="closeApp()">
                <svg width="12" height="12" viewBox="0 0 12 12"><line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5"/><line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
        </div>
    </div>

    <div class="main-content">
        <div class="card">
            <h1>{title}</h1>
            <p>{desc}</p>

            <div class="guide-box">
                <div class="guide-title">
                    <span>💡 零污染一键环境配置指南 / Zero-Pollution Setup</span>
                </div>
                <p style="margin: 4px 0 8px 0; font-size: 12px; color: #94a3b8;">
                    遵循 AGENTS.md 准则，我们不污染全局系统环境。在终端中执行以下命令即可快速创建专有虚拟环境：
                </p>
                <pre>cd D:\dev\AI-Studio\backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt</pre>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: #94a3b8;">
                    完成后点击下方「重试启动 (Retry Connection)」，软件将自动加载并启动服务。
                </p>
            </div>

            <div class="actions">
                <button class="btn" onclick="location.reload()">重试启动 (Retry Connection)</button>
                <button class="btn btn-secondary" onclick="closeApp()">关闭应用 (Exit)</button>
            </div>
        </div>
    </div>

    <script>
        function closeApp() {{
            if (window.__TAURI__ && window.__TAURI__.core) {{
                window.__TAURI__.core.invoke('close_app').catch(function() {{
                    window.close();
                }});
            }} else {{
                window.close();
            }}
        }}
        function minimizeApp() {{
            if (window.__TAURI__ && window.__TAURI__.core) {{
                window.__TAURI__.core.invoke('minimize_app');
            }}
        }}
    </script>
</body>
</html>"#,
                        title = diag_title,
                        desc = diag_desc,
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
