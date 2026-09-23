//! Unified CLI for Berry AI Studio Creative Execution & Management (M8).

use std::path::Path;
use crate::client::{BerryClient, CliCreativeResult};

fn get_flag_value(args: &[String], flag: &str) -> Option<String> {
    for i in 0..args.len() {
        if args[i] == flag && i + 1 < args.len() {
            return Some(args[i + 1].clone());
        }
    }
    None
}

fn has_flag(args: &[String], flag: &str) -> bool {
    args.iter().any(|a| a == flag)
}

pub fn handle_run_command(client: &BerryClient, args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Err("Action required for 'berry run'. Usage: berry run <txt2img|img2img|inpaint|upscale|txt2video|img2video> [options]".to_string());
    }

    let action = &args[0];
    let is_json = has_flag(args, "--json");

    let prompt = get_flag_value(args, "--prompt").unwrap_or_default();
    let negative_prompt = get_flag_value(args, "--negative-prompt")
        .unwrap_or_else(|| "low quality, blurry, deformed, bad anatomy".to_string());
    let engine = get_flag_value(args, "--engine").unwrap_or_else(|| "managed_comfyui".to_string());
    let model = get_flag_value(args, "--model")
        .unwrap_or_else(|| "v1-5-pruned-emaonly.safetensors".to_string());
    let aspect_ratio = get_flag_value(args, "--aspect-ratio").unwrap_or_else(|| "1:1".to_string());
    let seed: i64 = get_flag_value(args, "--seed")
        .and_then(|s| s.parse().ok())
        .unwrap_or(-1);
    let steps: i64 = get_flag_value(args, "--steps")
        .and_then(|s| s.parse().ok())
        .unwrap_or(20);
    let cfg: f64 = get_flag_value(args, "--cfg")
        .and_then(|s| s.parse().ok())
        .unwrap_or(7.0);
    let denoise: f64 = get_flag_value(args, "--denoise")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0.75);
    let fps: u32 = get_flag_value(args, "--fps")
        .and_then(|s| s.parse().ok())
        .unwrap_or(16);
    let frames: u32 = get_flag_value(args, "--frames")
        .and_then(|s| s.parse().ok())
        .unwrap_or(25);
    let motion: u32 = get_flag_value(args, "--motion")
        .and_then(|s| s.parse().ok())
        .unwrap_or(127);
    let upscale_factor: f64 = get_flag_value(args, "--upscale-factor")
        .and_then(|s| s.parse().ok())
        .unwrap_or(2.0);
    let output_path = get_flag_value(args, "--output");

    // Optional input image upload
    let mut input_image_id: Option<String> = None;
    if let Some(image_path_str) = get_flag_value(args, "--image") {
        let p = Path::new(&image_path_str);
        if !p.exists() {
            return Err(format!("Input image file not found: {}", image_path_str));
        }
        if !is_json {
            println!("[*] Uploading input image: {}", image_path_str);
        }
        let asset_id = client.upload_asset_from_file(p)?;
        input_image_id = Some(asset_id);
    }

    // Optional mask image upload
    let mut mask_image_id: Option<String> = None;
    if let Some(mask_path_str) = get_flag_value(args, "--mask") {
        let p = Path::new(&mask_path_str);
        if !p.exists() {
            return Err(format!("Input mask file not found: {}", mask_path_str));
        }
        if !is_json {
            println!("[*] Uploading mask image: {}", mask_path_str);
        }
        let asset_id = client.upload_asset_from_file(p)?;
        mask_image_id = Some(asset_id);
    }

    let payload = serde_json::json!({
        "action": action,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "engine_id": engine,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "seed": seed,
        "steps": steps,
        "cfg_scale": cfg,
        "denoise": denoise,
        "input_image_id": input_image_id,
        "mask_image_id": mask_image_id,
        "fps": fps,
        "num_frames": frames,
        "motion_bucket_id": motion,
        "upscale_factor": upscale_factor
    });

    if !is_json {
        println!("========================================================");
        println!("          Berry AI Studio - Task Dispatch");
        println!("========================================================");
        println!("Action       : {}", action);
        println!("Prompt       : \"{}\"", prompt);
        println!("Engine       : {}", engine);
        println!("Model        : {}", model);
        println!("Ratio / Seed : {} / {}", aspect_ratio, seed);
        println!("Executing task asynchronously...\n");
    }

    let result: CliCreativeResult = client.execute_creative(payload)?;

    if !result.success {
        let err = result.error_message.unwrap_or_else(|| "Unknown failure".to_string());
        if is_json {
            let json_err = serde_json::json!({ "success": false, "error": err });
            println!("{}", serde_json::to_string_pretty(&json_err).unwrap());
        } else {
            eprintln!("[ERROR] Execution failed: {}", err);
        }
        return Err(err);
    }

    // Handle output file download if requested
    let media_url = result.video_url.as_deref().or(result.image_url.as_deref());
    let mut saved_to: Option<String> = None;

    if let (Some(dest_str), Some(url)) = (output_path, media_url) {
        if !is_json {
            println!("[*] Downloading generated output to: {}", dest_str);
        }
        let bytes = client.download_asset_bytes(url)?;
        std::fs::write(&dest_str, bytes).map_err(|e| format!("Failed to write output file {}: {}", dest_str, e))?;
        saved_to = Some(dest_str);
    }

    if is_json {
        let mut out = serde_json::to_value(&result).unwrap_or(serde_json::Value::Null);
        if let Some(dest) = saved_to {
            out["saved_file"] = serde_json::Value::String(dest);
        }
        println!("{}", serde_json::to_string_pretty(&out).unwrap());
    } else {
        println!("========================================================");
        println!("                 Task Completed");
        println!("========================================================");
        println!("Status       : Success");
        println!("Task ID      : {}", result.task_id);
        println!("Dimensions   : {}x{}", result.width, result.height);
        if let Some(fps_val) = result.fps {
            println!("Framerate    : {} fps", fps_val);
        }
        if let Some(dur) = result.duration_seconds {
            println!("Duration     : {:.1}s", dur);
        }
        if let Some(url) = media_url {
            println!("Asset URL    : {}", url);
        }
        println!("Cached       : {}", if result.is_cached { "Yes (idempotent cache hit)" } else { "No (fresh inference)" });
        if let Some(dest) = saved_to {
            println!("Saved File   : {}", dest);
        }
        println!("========================================================\n");
    }

    Ok(())
}

pub fn handle_tasks_command(client: &BerryClient, args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Err("Subcommand required. Usage: berry tasks <list|cancel <task_id>>".to_string());
    }

    let is_json = has_flag(args, "--json");

    match args[0].as_str() {
        "list" => {
            let tasks = client.list_active_tasks()?;
            if is_json {
                println!("{}", serde_json::to_string_pretty(&tasks).unwrap());
            } else {
                println!("\nActive Creative Tasks:");
                if let Some(map) = tasks.as_object() {
                    if map.is_empty() {
                        println!("  (No in-flight creative tasks)");
                    } else {
                        for (task_id, info) in map {
                            println!("  - Task [{}] : action={}, engine={}",
                                task_id,
                                info.get("action").and_then(|v| v.as_str()).unwrap_or("?"),
                                info.get("engine").and_then(|v| v.as_str()).unwrap_or("?")
                            );
                        }
                    }
                }
                println!();
            }
        }
        "cancel" => {
            if args.len() < 2 {
                return Err("Usage: berry tasks cancel <task_id>".to_string());
            }
            let task_id = &args[1];
            let res = client.cancel_task(task_id)?;
            if is_json {
                println!("{}", serde_json::to_string_pretty(&res).unwrap());
            } else {
                println!("[OK] Task cancellation signal sent for {}", task_id);
            }
        }
        other => return Err(format!("Unknown tasks subcommand '{}'. Expected list, cancel.", other)),
    }

    Ok(())
}

pub fn handle_system_command(client: &BerryClient, args: &[String]) -> Result<(), String> {
    let is_json = has_flag(args, "--json");
    let info = client.get_system_info()?;

    if is_json {
        println!("{}", serde_json::to_string_pretty(&info).unwrap());
    } else {
        println!("\n========================================================");
        println!("               Berry AI Studio Diagnostics");
        println!("========================================================");
        if let Some(obj) = info.as_object() {
            for (k, v) in obj {
                println!("  {:<20} : {}", k, v);
            }
        }
        println!("========================================================\n");
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_flag_parsing() {
        let args = vec![
            "txt2img".to_string(),
            "--prompt".to_string(),
            "cyberpunk city".to_string(),
            "--json".to_string(),
            "--steps".to_string(),
            "30".to_string(),
        ];

        assert_eq!(get_flag_value(&args, "--prompt"), Some("cyberpunk city".to_string()));
        assert_eq!(get_flag_value(&args, "--steps"), Some("30".to_string()));
        assert_eq!(get_flag_value(&args, "--nonexistent"), None);

        assert!(has_flag(&args, "--json"));
        assert!(!has_flag(&args, "--yaml"));
    }
}
