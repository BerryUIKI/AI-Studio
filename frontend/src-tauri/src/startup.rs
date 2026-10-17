//! Backend-independent onboarding commands, confined to the local startup page.
use crate::AppState;
use std::sync::atomic::Ordering;
use tauri::Manager;

#[derive(Clone, serde::Serialize)]
pub struct StartupStatus {
    pub phase: String,
    pub details: String,
    pub environment_path: String,
    pub can_install: bool,
    pub error_code: String,
    pub volume: String,
    pub available_bytes: Option<u64>,
    pub required_bytes: Option<u64>,
}

fn local_page(window: &tauri::WebviewWindow) -> Result<(), String> {
    let url = window.url().map_err(|_| "Cannot verify setup page")?;
    if permits_setup(&url) {
        Ok(())
    } else {
        Err("Environment setup is available only from the local startup page".into())
    }
}

fn permits_setup(url: &tauri::Url) -> bool {
    let bundled = (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || (url.scheme() == "http" && url.host_str() == Some("tauri.localhost"));
    let development = cfg!(debug_assertions)
        && url.scheme() == "http"
        && url.port() == Some(5173)
        && ["localhost", "127.0.0.1"].contains(&url.host_str().unwrap_or(""));
    url.username().is_empty()
        && url.path() == "/startup.html"
        && ((bundled && url.port().is_none()) || development)
}

#[cfg(test)]
mod tests {
    use super::permits_setup;
    #[test]
    fn setup_commands_cannot_be_called_from_backend_or_external_pages() {
        for url in [
            "tauri://localhost/startup.html",
            "http://tauri.localhost/startup.html",
        ] {
            assert!(permits_setup(&tauri::Url::parse(url).unwrap()));
        }
        for url in [
            "http://127.0.0.1:8000/startup.html",
            "https://example.com/startup.html",
            "tauri://localhost/index.html",
            "http://tauri.localhost:8000/startup.html",
            "tauri://untrusted@localhost/startup.html",
        ] {
            assert!(!permits_setup(&tauri::Url::parse(url).unwrap()));
        }
    }
}

#[tauri::command]
pub fn startup_status(
    window: tauri::WebviewWindow,
    state: tauri::State<AppState>,
) -> Result<StartupStatus, String> {
    local_page(&window)?;
    Ok(state
        .startup
        .lock()
        .map_err(|_| "Setup state unavailable")?
        .clone())
}

#[tauri::command]
pub async fn discover_environments(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
) -> Result<Vec<serde_json::Value>, String> {
    local_page(&window)?;
    let root = app.state::<AppState>().root_dir.clone();
    tauri::async_runtime::spawn_blocking(move || berry_runtime::environments::discover(&root))
        .await
        .map_err(|_| "Environment discovery failed".into())
}

#[tauri::command]
pub async fn inspect_environment(
    window: tauri::WebviewWindow,
    path: String,
) -> Result<serde_json::Value, String> {
    local_page(&window)?;
    tauri::async_runtime::spawn_blocking(move || {
        berry_runtime::environments::inspect(std::path::Path::new(&path))
    })
    .await
    .map_err(|_| "Environment inspection failed".into())
}

#[tauri::command]
pub fn cancel_environment_setup(
    window: tauri::WebviewWindow,
    state: tauri::State<AppState>,
) -> Result<(), String> {
    local_page(&window)?;
    state.setup_cancel.store(true, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
pub async fn prepare_environment(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    action: String,
    path: Option<String>,
    language: Option<String>,
) -> Result<(), String> {
    local_page(&window)?;
    if !["install", "retry", "existing"].contains(&action.as_str()) {
        return Err("Unknown setup action".into());
    }
    let state = app.state::<AppState>();
    if state
        .setup_running
        .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .is_err()
    {
        return Err("Environment setup is already running".into());
    }
    state.setup_cancel.store(false, Ordering::SeqCst);
    state.startup.lock().unwrap().phase = "validating".into();
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let app = handle;
        let state = app.state::<AppState>();
        let result = (|| -> Result<(), berry_runtime::setup_error::SetupError> {
            if action != "retry" && state.backend_child.lock().unwrap().as_mut()
                .is_some_and(|child| child.try_wait().ok().flatten().is_none()) {
                return Err("The application service is still running. Retry startup before changing its environment.".into());
            }
            if action == "install" {
                berry_runtime::bootstrap::install(&state.root_dir, &state.setup_cancel, |phase| {
                    state.startup.lock().unwrap().phase = phase.to_owned();
                })?;
                berry_runtime::environments::clear(&state.root_dir)?;
            } else if action == "existing" {
                let path = path.ok_or("Choose an existing Python interpreter")?;
                berry_runtime::environments::select(&state.root_dir, std::path::Path::new(&path))?;
            }
            if state.setup_cancel.load(Ordering::SeqCst) { return Err("Environment setup cancelled".into()); }
            let python = berry_runtime::find_python_executable(&state.root_dir)?;
            if !berry_runtime::bootstrap::runtime_usable(&python) { return Err("Selected environment needs the required application dependencies".into()); }
            state.startup.lock().unwrap().phase = "starting".into();
            let mut child = state.backend_child.lock().unwrap();
            // Never replace a still-owned process or take ownership of an existing service.
            if let Some(process) = child.as_mut() {
                if process.try_wait().map_err(|_| "Cannot check owned backend")?.is_some() { *child = None; }
            }
            if child.is_none() { *child = berry_runtime::spawn_backend(&state.root_dir, state.port)?; }
            drop(child);
            let started = std::time::Instant::now();
            loop {
                if state.setup_cancel.load(Ordering::SeqCst) { return Err("Environment setup cancelled".into()); }
                if berry_runtime::is_backend_healthy(state.port) { break; }
                if started.elapsed().as_secs() >= 30 { return Err(berry_runtime::setup_error::SetupError::new("service", "The application service did not become ready")); }
                let mut child = state.backend_child.lock().unwrap();
                if let Some(process) = child.as_mut() {
                    if process.try_wait().map_err(|_| "Cannot check owned backend")?.is_some() {
                        *child = None;
                        return Err(berry_runtime::setup_error::SetupError::new("service", "The application service stopped"));
                    }
                }
                drop(child);
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
            if state.setup_cancel.load(Ordering::SeqCst) { return Err("Environment setup cancelled".into()); }
            let mut status = state.startup.lock().unwrap();
            status.phase = "ready".into(); status.details.clear();
            drop(status);
            if let Some(window) = app.get_webview_window("main") {
                let mut url = tauri::Url::parse(&format!("http://127.0.0.1:{}", state.port)).unwrap();
                if let Some(locale) = language.filter(|value| ["system", "en", "zh-CN", "ja", "ko", "fr", "de", "es", "ru"].contains(&value.as_str())) {
                    url.query_pairs_mut().append_pair("setupLanguage", &locale);
                }
                window.navigate(url).map_err(|_| "Could not open the workspace")?;
            }
            Ok(())
        })();
        if let Err(error) = &result {
            let mut status = state.startup.lock().unwrap();
            status.phase = if state.setup_cancel.load(Ordering::SeqCst) { "cancelled" } else { "failed" }.into();
            status.details = error.detail.clone();
            status.error_code = error.code.into();
            status.volume = error.volume.clone();
            status.available_bytes = error.available_bytes;
            status.required_bytes = error.required_bytes;
        }
        state.setup_running.store(false, Ordering::SeqCst);
        result.map_err(|error| error.detail)
    }).await.map_err(|_| "Environment preparation was interrupted".to_owned())?
}
