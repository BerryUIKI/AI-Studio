//! Update manager for Berry application and managed engines (L08, L12).

use crate::client::BerryClient;

pub struct UpdateManager<'a> {
    client: &'a BerryClient,
}

impl<'a> UpdateManager<'a> {
    pub fn new(client: &'a BerryClient) -> Self {
        Self { client }
    }

    pub fn check_updates(&self) -> Result<(), String> {
        println!("\nChecking updates for Berry AI Studio and managed engines...");
        let data = self.client.check_updates()?;

        if let Some(app) = data.get("app") {
            let curr = app.get("current_version").and_then(|v| v.as_str()).unwrap_or("0.1.0");
            let latest = app.get("latest_version").and_then(|v| v.as_str()).unwrap_or("0.1.0");
            let avail = app.get("update_available").and_then(|v| v.as_bool()).unwrap_or(false);

            println!("\n=== Berry AI Studio Application ===");
            println!("Installed Version : {}", curr);
            println!("Latest Version    : {}", latest);
            println!("Update Available  : {}", if avail { "YES" } else { "No (Up to date)" });
        }

        if let Some(engines) = data.get("engines") {
            println!("\n=== Managed Local Inference Engines ===");
            if let Some(comfy) = engines.get("comfyui") {
                let installed = comfy.get("installed").and_then(|v| v.as_bool()).unwrap_or(false);
                println!("Managed ComfyUI   : {}", if installed { "Installed" } else { "Not Installed" });
            }
            if let Some(webui) = engines.get("webui") {
                let installed = webui.get("installed").and_then(|v| v.as_bool()).unwrap_or(false);
                println!("Managed WebUI     : {}", if installed { "Installed" } else { "Not Installed" });
            }
        }

        Ok(())
    }

    pub fn update_engine(&self, engine_type: &str) -> Result<(), String> {
        println!("\nInitiating safe update for managed engine '{}' (L12)...", engine_type);
        println!("Checking active tasks and recording rollback checkpoint...");

        let manifest = self.client.update_engine(engine_type)?;

        println!("\n=== Update Result ===");
        println!("Engine   : {}", manifest.engine_type);
        println!("Status   : {}", manifest.status);
        if let Some(prev) = &manifest.previous_commit {
            println!("Previous Commit : {}", prev);
        }
        if let Some(target) = &manifest.target_commit {
            println!("Target Commit   : {}", target);
        }
        if manifest.rollback_performed {
            println!("Rollback Performed : YES (restored to previous working commit)");
        }
        if let Some(err) = &manifest.error_message {
            println!("Details  : {}", err);
        }

        Ok(())
    }

    pub fn update_app(&self) -> Result<(), String> {
        println!("\nInitiating Berry AI Studio application update (L08)...");
        let res = self.client.trigger_app_update()?;

        let mode = res.get("mode").and_then(|v| v.as_str()).unwrap_or("unknown");
        let status = res.get("status").and_then(|v| v.as_str()).unwrap_or("unknown");
        let message = res.get("message").and_then(|v| v.as_str()).unwrap_or("");

        println!("\n=== Application Update Result ===");
        println!("Mode    : {}", mode);
        println!("Status  : {}", status);
        println!("Message : {}", message);

        if let Some(details) = res.get("details").and_then(|v| v.as_str()) {
            println!("Details : {}", details);
        }

        if let Some(url) = res.get("download_url").and_then(|v| v.as_str()) {
            println!("Download Package : {}", url);
        }

        if let Some(notes) = res.get("notes").and_then(|v| v.as_str()) {
            println!("Safety Notice    : {}", notes);
        }

        Ok(())
    }
}

