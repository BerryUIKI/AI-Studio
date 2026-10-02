//! Berry AI Studio - Launcher & Environment Manager (L01-L12).

mod backend;
mod cli;
mod client;
mod port;
mod single_instance;
mod update;

use std::env;
use std::path::PathBuf;

use client::BerryClient;
use port::{check_port_status, PortStatus};
use single_instance::try_acquire_single_instance;
use update::UpdateManager;

const DEFAULT_PORT: u16 = 8000;
const MUTEX_NAME: &str = "Global\\BerryAIStudioLauncherMutex";

fn resolve_root_dir() -> PathBuf {
    // Current executable directory or current working directory
    if let Ok(exe_path) = env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            // Check if backend directory exists in parent or grandparent
            if parent.join("backend").is_dir() {
                return parent.to_path_buf();
            }
            if let Some(grandparent) = parent.parent() {
                if grandparent.join("backend").is_dir() {
                    return grandparent.to_path_buf();
                }
                if let Some(ggp) = grandparent.parent() {
                    if ggp.join("backend").is_dir() {
                        return ggp.to_path_buf();
                    }
                }
            }
        }
    }
    // Fallback to current dir
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn print_help() {
    println!("Berry AI Studio - Launcher and Environment Manager");
    println!("\nUsage:");
    println!("  berry                       Launch or focus Berry creative workspace");
    println!("  berry manager               Open the Environment Manager directly");
    println!("  berry status                Display unified status of core, engines, and models");
    println!("  berry stop [--force]        Gracefully stop Berry AI Studio and active processes");
    println!("  berry engine <action> <type> Manage engine lifecycle (start, stop, install, update)");
    println!("  berry models <action> [...]  Manage model inventory (list, rescan, add, remove)");
    println!("  berry update <check|app|engine> Manage application and engine updates");
    println!("  berry run <action> [options] Execute creative workflows from CLI (txt2img, img2img, upscale, txt2video, img2video)");
    println!("  berry tasks <list|cancel>   Inspect or cancel background execution tasks");
    println!("  berry system [--json]       Display hardware readiness and engine availability");
    println!("  berry help                  Show this help screen");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let root_dir = resolve_root_dir();
    let port = env::var("BERRY_PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(DEFAULT_PORT);

    let client = BerryClient::new(port);

    if args.len() > 1 {
        match args[1].as_str() {
            "run" => {
                if let Err(e) = cli::handle_run_command(&client, &args[2..]) {
                    eprintln!("[ERROR] {}", e);
                    std::process::exit(1);
                }
            }

            "tasks" => {
                if let Err(e) = cli::handle_tasks_command(&client, &args[2..]) {
                    eprintln!("[ERROR] {}", e);
                    std::process::exit(1);
                }
            }

            "system" => {
                if let Err(e) = cli::handle_system_command(&client, &args[2..]) {
                    eprintln!("[ERROR] {}", e);
                    std::process::exit(1);
                }
            }
            "status" => {
                match client.get_status() {
                    Ok(status) => {
                        println!("\n========================================================");
                        println!("            Berry AI Studio - Environment Status");
                        println!("========================================================");
                        println!("Application : {} v{}", status.app_name, status.version);
                        println!("Core PID    : {}", status.pid);
                        println!("Uptime      : {:.1}s", status.uptime_seconds);
                        println!("Loopback    : http://127.0.0.1:{}", status.port);
                        println!("Frontend    : {}", if status.frontend_packaged { "Packaged (Production)" } else { "Development / Missing" });
                        println!("Active Tasks: {}", status.active_tasks);

                        println!("\n[Local Inference Engines]");
                        println!("  Managed ComfyUI : {} ({})", status.managed_comfyui.status, status.managed_comfyui.endpoint_url);
                        println!("  Managed WebUI   : {} ({})", status.managed_webui.status, status.managed_webui.endpoint_url);
                        for ext in &status.external_engines {
                            println!("  External Engine : {} [{}] ({})", ext.name, ext.status, ext.endpoint_url);
                        }

                        println!("\n[Cloud & Assets]");
                        println!("  Cloud BYOK Keys : {} provider(s) configured", status.cloud_providers_configured);
                        println!("  Models Indexed  : {} record(s)", status.models_indexed);
                        println!("========================================================\n");
                    }
                    Err(e) => {
                        eprintln!("[ERROR] Berry AI Studio is not currently running on port {}: {}", port, e);
                        std::process::exit(1);
                    }
                }
            }

            "stop" => {
                let force = args.iter().any(|a| a == "--force");
                println!("Requesting Berry AI Studio shutdown (port {}, force: {})...", port, force);
                match client.shutdown(force) {
                    Ok(res) => {
                        println!("[OK] {}", res.message);
                        if res.active_tasks_cancelled > 0 {
                            println!("     Cancelled {} active task(s).", res.active_tasks_cancelled);
                        }
                        if !res.managed_engines_stopped.is_empty() {
                            println!("     Stopped managed engine(s): {:?}", res.managed_engines_stopped);
                        }
                    }
                    Err(e) => {
                        eprintln!("[ERROR] Shutdown failed: {}", e);
                        std::process::exit(1);
                    }
                }
            }

            "manager" => {
                let url = format!("http://127.0.0.1:{}/#manager", port);
                println!("Opening Environment Manager: {}", url);
                single_instance::open_browser(&url);
            }

            "engine" => {
                if args.len() < 4 {
                    eprintln!("Usage: berry engine <start|stop|install|update> <comfyui|webui>");
                    std::process::exit(1);
                }
                let action = &args[2];
                let engine = &args[3];
                match action.as_str() {
                    "start" => {
                        if let Err(e) = client.start_engine(engine) {
                            eprintln!("[ERROR] {}", e);
                            std::process::exit(1);
                        }
                        println!("[OK] Started managed {}", engine);
                    }
                    "stop" => {
                        if let Err(e) = client.stop_engine(engine) {
                            eprintln!("[ERROR] {}", e);
                            std::process::exit(1);
                        }
                        println!("[OK] Stopped managed {}", engine);
                    }
                    "install" => {
                        if let Err(e) = client.install_engine(engine) {
                            eprintln!("[ERROR] {}", e);
                            std::process::exit(1);
                        }
                        println!("[OK] Triggered installation for {}", engine);
                    }
                    "update" => {
                        let updater = UpdateManager::new(&client);
                        if let Err(e) = updater.update_engine(engine) {
                            eprintln!("[ERROR] {}", e);
                            std::process::exit(1);
                        }
                    }
                    _ => {
                        eprintln!("Unknown engine action '{}'. Expected start, stop, install, update.", action);
                        std::process::exit(1);
                    }
                }
            }

            "models" => {
                if args.len() < 3 {
                    eprintln!("Usage: berry models <list|rescan|roots|add-root <path> <label>|remove-root <id>>");
                    std::process::exit(1);
                }
                let sub = &args[2];
                match sub.as_str() {
                    "list" => match client.list_models() {
                        Ok(models) => {
                            println!("\nDiscovered Models ({}):", models.len());
                            for m in models {
                                println!("  - {} [{}] ({:.1} MB, {})", m.name, m.architecture, m.size_mb, m.file_path);
                            }
                        }
                        Err(e) => eprintln!("[ERROR] {}", e),
                    },
                    "rescan" => match client.rescan_models() {
                        Ok(models) => println!("[OK] Rescan complete: {} model(s) indexed.", models.len()),
                        Err(e) => eprintln!("[ERROR] {}", e),
                    },
                    "roots" => match client.list_model_roots() {
                        Ok(roots) => {
                            println!("\nConfigured Model Roots ({}):", roots.len());
                            for r in roots {
                                println!("  - {} [{}] -> {} (exists: {}, found: {})", r.label, r.id, r.path, r.exists, r.models_found);
                            }
                        }
                        Err(e) => eprintln!("[ERROR] {}", e),
                    },
                    "add-root" => {
                        if args.len() < 5 {
                            eprintln!("Usage: berry models add-root <directory_path> <label>");
                            std::process::exit(1);
                        }
                        match client.add_model_root(&args[3], &args[4]) {
                            Ok(root) => println!("[OK] Added model root '{}' (ID: {})", root.label, root.id),
                            Err(e) => eprintln!("[ERROR] {}", e),
                        }
                    }
                    "remove-root" => {
                        if args.len() < 4 {
                            eprintln!("Usage: berry models remove-root <root_id>");
                            std::process::exit(1);
                        }
                        match client.remove_model_root(&args[3]) {
                            Ok(_) => println!("[OK] Removed model root '{}'", args[3]),
                            Err(e) => eprintln!("[ERROR] {}", e),
                        }
                    }
                    _ => eprintln!("Unknown models subcommand '{}'", sub),
                }
            }

            "update" => {
                let updater = UpdateManager::new(&client);
                if args.len() > 2 {
                    match args[2].as_str() {
                        "app" => {
                            if let Err(e) = updater.update_app() {
                                eprintln!("[ERROR] {}", e);
                                std::process::exit(1);
                            }
                        }
                        "engine" => {
                            let engine = if args.len() > 3 { &args[3] } else { "comfyui" };
                            if let Err(e) = updater.update_engine(engine) {
                                eprintln!("[ERROR] {}", e);
                                std::process::exit(1);
                            }
                        }
                        "check" => {
                            if let Err(e) = updater.check_updates() {
                                eprintln!("[ERROR] {}", e);
                                std::process::exit(1);
                            }
                        }
                        other => {
                            eprintln!("Unknown update target '{}'. Usage: berry update <check|app|engine [comfyui|webui]>", other);
                            std::process::exit(1);
                        }
                    }
                } else {
                    if let Err(e) = updater.check_updates() {
                        eprintln!("[ERROR] {}", e);
                        std::process::exit(1);
                    }
                }
            }

            "help" | "-h" | "--help" => print_help(),
            other => {
                eprintln!("Unknown command '{}'", other);
                print_help();
                std::process::exit(1);
            }
        }
        return;
    }

    // Default action: Start or focus Berry AI Studio
    // 1. Check Windows single-instance mutex (L03)
    let _instance_guard = match try_acquire_single_instance(MUTEX_NAME) {
        Some(guard) => guard,
        None => {
            // Another launcher process is already active: focus existing workspace
            println!("[*] Berry AI Studio is already running — focusing active workspace.");
            let url = format!("http://127.0.0.1:{}", port);
            single_instance::open_browser(&url);
            return;
        }
    };

    // 2. Check port status (L03)
    match check_port_status(port) {
        PortStatus::OccupiedByBerry => {
            println!("[*] Active Berry instance detected on port {} — opening workspace.", port);
            let url = format!("http://127.0.0.1:{}", port);
            single_instance::open_browser(&url);
            return;
        }
        PortStatus::OccupiedByNonBerry => {
            eprintln!("\n[ERROR] Port {} is occupied by an external application (non-Berry).", port);
            eprintln!("Action required:");
            eprintln!("  1. Free port {} by closing the conflicting application, OR", port);
            eprintln!("  2. Run Berry on a custom port: set BERRY_PORT=8001 && berry\n");
            std::process::exit(1);
        }
        PortStatus::Free => {
            // Port is clear, proceed with launch
        }
    }

    // 3. Supervised launch (L01, L02)
    let mut supervisor = backend::BackendSupervisor::new(root_dir, port);
    if let Err(e) = supervisor.start() {
        eprintln!("\n[FATAL] Startup failed: {}", e);
        std::process::exit(1);
    }

    // 4. Open workspace after readiness
    supervisor.open_workspace();

    // 5. Keep running as environment manager / process supervisor (L07)
    if let Err(e) = supervisor.wait() {
        eprintln!("[ERROR] Supervisor error: {}", e);
    }
}
