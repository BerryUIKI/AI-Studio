//! Versioned Local API Client for Berry AI Studio (L11).

use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineConnection {
    pub id: String,
    pub name: String,
    pub engine_type: String,
    pub ownership: String,
    pub endpoint_url: String,
    pub status: String,
    pub native_ui_url: Option<String>,
    pub version: Option<String>,
    pub vram_free_mb: Option<i64>,
    pub capabilities: Vec<String>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LauncherConfig {
    pub stop_managed_engines_on_exit: bool,
    pub default_engine: String,
    pub browser_auto_open: bool,
    pub port: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManagerStatusResponse {
    pub app_name: String,
    pub version: String,
    pub pid: u32,
    pub uptime_seconds: f64,
    pub port: u16,
    pub frontend_packaged: bool,
    pub managed_comfyui: EngineConnection,
    pub managed_webui: EngineConnection,
    pub external_engines: Vec<EngineConnection>,
    pub cloud_providers_configured: usize,
    pub models_indexed: usize,
    pub active_tasks: usize,
    pub launcher_config: LauncherConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShutdownResponse {
    pub status: String,
    pub message: String,
    pub active_tasks_cancelled: usize,
    pub managed_engines_stopped: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelRecord {
    pub id: String,
    pub name: String,
    pub file_path: String,
    pub category: String,
    pub architecture: String,
    pub format: String,
    pub size_mb: f64,
    pub engine_compatibility: Vec<String>,
    pub is_ready: bool,
    pub missing_dependencies: Vec<String>,
    pub guidance: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelRoot {
    pub id: String,
    pub path: String,
    pub label: String,
    pub engine_type: Option<String>,
    pub exists: bool,
    pub models_found: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineUpdateManifest {
    pub engine_type: String,
    pub status: String,
    pub previous_commit: Option<String>,
    pub target_commit: Option<String>,
    pub updated_at: Option<String>,
    pub error_message: Option<String>,
    pub rollback_supported: bool,
    pub rollback_performed: bool,
}

pub struct BerryClient {
    base_url: String,
    agent: ureq::Agent,
}

impl BerryClient {
    pub fn new(port: u16) -> Self {
        let agent = ureq::Agent::config_builder()
            .timeout_global(Some(Duration::from_secs(10)))
            .build()
            .new_agent();
        Self {
            base_url: format!("http://127.0.0.1:{}", port),
            agent,
        }
    }

    pub fn get_status(&self) -> Result<ManagerStatusResponse, String> {
        let url = format!("{}/api/v1/manager/status", self.base_url);
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("HTTP request failed: {}", e))?;
        resp.body_mut().read_json::<ManagerStatusResponse>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn shutdown(&self, force: bool) -> Result<ShutdownResponse, String> {
        let url = format!("{}/api/v1/manager/shutdown", self.base_url);
        let payload = serde_json::json!({ "force": force });
        let mut resp = self.agent.post(&url)
            .send_json(payload)
            .map_err(|e| format!("Shutdown request failed: {}", e))?;
        resp.body_mut().read_json::<ShutdownResponse>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn list_models(&self) -> Result<Vec<ModelRecord>, String> {
        let url = format!("{}/api/v1/models", self.base_url);
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("Failed to list models: {}", e))?;
        resp.body_mut().read_json::<Vec<ModelRecord>>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn rescan_models(&self) -> Result<Vec<ModelRecord>, String> {
        let url = format!("{}/api/v1/models/rescan", self.base_url);
        let mut resp = self.agent.post(&url).send_empty().map_err(|e| format!("Failed to rescan models: {}", e))?;
        resp.body_mut().read_json::<Vec<ModelRecord>>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn list_model_roots(&self) -> Result<Vec<ModelRoot>, String> {
        let url = format!("{}/api/v1/models/roots", self.base_url);
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("Failed to list roots: {}", e))?;
        resp.body_mut().read_json::<Vec<ModelRoot>>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn add_model_root(&self, path: &str, label: &str) -> Result<ModelRoot, String> {
        let url = format!("{}/api/v1/models/roots", self.base_url);
        let payload = serde_json::json!({ "path": path, "label": label });
        let mut resp = self.agent.post(&url).send_json(payload).map_err(|e| format!("Failed to add root: {}", e))?;
        resp.body_mut().read_json::<ModelRoot>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn remove_model_root(&self, root_id: &str) -> Result<(), String> {
        let url = format!("{}/api/v1/models/roots/{}", self.base_url, root_id);
        self.agent.delete(&url).call().map_err(|e| format!("Failed to remove root: {}", e))?;
        Ok(())
    }

    pub fn start_engine(&self, engine_type: &str) -> Result<(), String> {
        let path = if engine_type == "webui" { "webui/start" } else { "start" };
        let url = format!("{}/api/v1/runtime/{}", self.base_url, path);
        self.agent.post(&url).send_empty().map_err(|e| format!("Failed to start {}: {}", engine_type, e))?;
        Ok(())
    }

    pub fn stop_engine(&self, engine_type: &str) -> Result<(), String> {
        let path = if engine_type == "webui" { "webui/stop" } else { "stop" };
        let url = format!("{}/api/v1/runtime/{}", self.base_url, path);
        self.agent.post(&url).send_empty().map_err(|e| format!("Failed to stop {}: {}", engine_type, e))?;
        Ok(())
    }

    pub fn install_engine(&self, engine_type: &str) -> Result<(), String> {
        let url = format!("{}/api/v1/runtime/{}/install", self.base_url, engine_type);
        self.agent.post(&url).send_empty().map_err(|e| format!("Failed to trigger install: {}", e))?;
        Ok(())
    }

    pub fn update_engine(&self, engine_type: &str) -> Result<EngineUpdateManifest, String> {
        let url = format!("{}/api/v1/runtime/{}/update", self.base_url, engine_type);
        let mut resp = self.agent.post(&url).send_empty().map_err(|e| format!("Failed to update engine: {}", e))?;
        resp.body_mut().read_json::<EngineUpdateManifest>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn check_updates(&self) -> Result<serde_json::Value, String> {
        let url = format!("{}/api/v1/updates/check", self.base_url);
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("Failed to check updates: {}", e))?;
        resp.body_mut().read_json::<serde_json::Value>().map_err(|e| format!("JSON decode failed: {}", e))
    }
}
