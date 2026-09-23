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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CliCreativeResult {
    pub success: bool,
    pub task_id: String,
    pub asset_id: Option<String>,
    pub image_url: Option<String>,
    pub video_url: Option<String>,
    pub width: u32,
    pub height: u32,
    pub duration_seconds: Option<f64>,
    pub fps: Option<u32>,
    pub provenance: Option<serde_json::Value>,
    pub is_cached: bool,
    pub error_message: Option<String>,
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

    pub fn trigger_app_update(&self) -> Result<serde_json::Value, String> {
        let url = format!("{}/api/v1/updates/app", self.base_url);
        let mut resp = self.agent.post(&url).send_empty().map_err(|e| format!("Failed to update application: {}", e))?;
        resp.body_mut().read_json::<serde_json::Value>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn execute_creative(&self, payload: serde_json::Value) -> Result<CliCreativeResult, String> {
        let url = format!("{}/api/v1/creative/execute", self.base_url);
        let creative_agent = ureq::Agent::config_builder()
            .timeout_global(Some(Duration::from_secs(300)))
            .build()
            .new_agent();
        let mut resp = creative_agent.post(&url)
            .send_json(payload)
            .map_err(|e| format!("Creative execution request failed: {}", e))?;
        resp.body_mut().read_json::<CliCreativeResult>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn download_asset_bytes(&self, path_or_url: &str) -> Result<Vec<u8>, String> {
        let url = if path_or_url.starts_with("http") {
            path_or_url.to_string()
        } else {
            format!("{}{}", self.base_url, path_or_url)
        };
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("Failed to download asset from {}: {}", url, e))?;
        let mut bytes = Vec::new();
        std::io::Read::read_to_end(&mut resp.body_mut().as_reader(), &mut bytes)
            .map_err(|e| format!("Failed to read asset bytes: {}", e))?;
        Ok(bytes)
    }

    pub fn list_active_tasks(&self) -> Result<serde_json::Value, String> {
        let url = format!("{}/api/v1/tasks/active", self.base_url);
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("Failed to list active tasks: {}", e))?;
        resp.body_mut().read_json::<serde_json::Value>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn cancel_task(&self, task_id: &str) -> Result<serde_json::Value, String> {
        let url = format!("{}/api/v1/tasks/{}/cancel", self.base_url, task_id);
        let mut resp = self.agent.post(&url).send_empty().map_err(|e| format!("Failed to cancel task {}: {}", task_id, e))?;
        resp.body_mut().read_json::<serde_json::Value>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn get_system_info(&self) -> Result<serde_json::Value, String> {
        let url = format!("{}/api/v1/system/info", self.base_url);
        let mut resp = self.agent.get(&url).call().map_err(|e| format!("Failed to get system info: {}", e))?;
        resp.body_mut().read_json::<serde_json::Value>().map_err(|e| format!("JSON decode failed: {}", e))
    }

    pub fn upload_asset_from_file(&self, file_path: &std::path::Path) -> Result<String, String> {
        let bytes = std::fs::read(file_path).map_err(|e| format!("Failed to read file {}: {}", file_path.display(), e))?;
        let filename = file_path.file_name().and_then(|n| n.to_str()).unwrap_or("input_asset.png");
        let b64 = base64_encode(&bytes);
        let url = format!("{}/api/v1/creative/upload-base64", self.base_url);
        let is_video = filename.ends_with(".mp4") || filename.ends_with(".webm");
        let payload = serde_json::json!({
            "filename": filename,
            "content_base64": b64,
            "media_type": if is_video { "video" } else { "image" }
        });
        let mut resp = self.agent.post(&url)
            .send_json(payload)
            .map_err(|e| format!("Failed to upload asset: {}", e))?;
        let res: serde_json::Value = resp.body_mut().read_json().map_err(|e| format!("JSON decode failed: {}", e))?;
        res.get("id").and_then(|id| id.as_str()).map(|s| s.to_string()).ok_or_else(|| "Missing asset ID in response".to_string())
    }
}

pub fn base64_encode(data: &[u8]) -> String {
    const CHARSET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::with_capacity((data.len() + 2) / 3 * 4);
    for chunk in data.chunks(3) {
        let b0 = chunk[0] as usize;
        let b1 = if chunk.len() > 1 { chunk[1] as usize } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as usize } else { 0 };
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARSET[(triple >> 18) & 0x3F] as char);
        result.push(CHARSET[(triple >> 12) & 0x3F] as char);
        if chunk.len() > 1 {
            result.push(CHARSET[(triple >> 6) & 0x3F] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(CHARSET[triple & 0x3F] as char);
        } else {
            result.push('=');
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_base64_encode() {
        assert_eq!(base64_encode(b""), "");
        assert_eq!(base64_encode(b"f"), "Zg==");
        assert_eq!(base64_encode(b"fo"), "Zm8=");
        assert_eq!(base64_encode(b"foo"), "Zm9v");
        assert_eq!(base64_encode(b"Berry AI Studio"), "QmVycnkgQUkgU3R1ZGlv");
    }
}



