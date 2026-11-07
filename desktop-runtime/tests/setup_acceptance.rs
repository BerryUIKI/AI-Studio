//! Explicit, networked acceptance probe; never executed by ordinary test runs.
#[test]
#[ignore = "Downloads an isolated Python runtime; requires explicit local fixture paths"]
fn cancelled_setup_can_retry_and_existing_environment_selection_is_read_only() {
    use berry_runtime::{bootstrap, environments};
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicBool, Ordering};
    let root = PathBuf::from(
        std::env::var_os("BERRY_SETUP_ACCEPTANCE_ROOT").expect("Set a disposable fixture root"),
    );
    let data = PathBuf::from(std::env::var_os("BERRY_DATA_DIR").expect("Set disposable app data"));
    assert!(root.is_absolute() && data.is_absolute() && data.starts_with(&root));
    assert!(
        !bootstrap::managed_python(&root).is_some(),
        "Use a fresh fixture"
    );
    let cancel = AtomicBool::new(false);
    let result = bootstrap::install(&root, &cancel, |stage| {
        println!("cancel probe: {stage}");
        if stage == "downloading" {
            assert!(bootstrap::install(&root, &AtomicBool::new(false), |_| {})
                .unwrap_err()
                .contains("already running"));
            cancel.store(true, Ordering::SeqCst);
        }
    });
    assert!(result.unwrap_err().contains("cancelled"));
    assert!(bootstrap::managed_python(&root).is_none());
    bootstrap::install(&root, &AtomicBool::new(false), |stage| {
        println!("retry: {stage}")
    })
    .unwrap();
    let python = bootstrap::managed_python(&root).unwrap();
    assert_eq!(environments::inspect(&python)["ready"], true);
    let before = std::fs::metadata(&python).unwrap().modified().unwrap();
    environments::select(&root, &python).unwrap();
    assert_eq!(environments::selected(&root).unwrap(), Some(python.clone()));
    environments::select(&root, &python).unwrap();
    assert_eq!(
        std::fs::metadata(&python).unwrap().modified().unwrap(),
        before
    );
    environments::clear(&root).unwrap();
    assert!(environments::selected(&root).unwrap().is_none());
    println!("Validated Python: {}", python.display());
}

#[test]
#[ignore = "Starts a real backend using an explicitly supplied existing environment"]
fn existing_environment_can_start_the_workspace_without_installation() {
    use berry_runtime::{bootstrap, environments};
    use std::path::PathBuf;
    let root = PathBuf::from(std::env::var_os("BERRY_SOURCE_ROOT").expect("Set source root"));
    let data = PathBuf::from(std::env::var_os("BERRY_DATA_DIR").expect("Set disposable app data"));
    let python = PathBuf::from(std::env::var_os("BERRY_EXISTING_PYTHON").expect("Set an existing complete Python environment"));
    assert!(root.is_absolute() && data.is_absolute() && data.starts_with(root.join(".cache")));
    assert_eq!(environments::inspect(&python)["ready"], true);
    let before = std::fs::metadata(&python).unwrap().modified().unwrap();
    environments::select(&root, &python).unwrap();
    assert_eq!(environments::selected(&root).unwrap(), Some(python.clone()));
    environments::select(&root, &python).unwrap();
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    drop(listener);
    let mut child = berry_runtime::spawn_backend(&root, port).unwrap();
    assert!(child.is_some(), "The acceptance fixture must own its backend");
    let ready = berry_runtime::wait_for_backend_ready(port, 30, &mut child);
    let (shutdown, _) = berry_runtime::shutdown_backend(port, child, berry_runtime::ShutdownMode::StopOwned {
        force: true, stop_managed_engines: Some(false),
    });
    assert!(ready, "The selected environment must start the real Berry service");
    assert!(matches!(shutdown, berry_runtime::ShutdownResult::Completed));
    assert_eq!(std::fs::metadata(&python).unwrap().modified().unwrap(), before);
    let selected = bootstrap::runtime_dir(&root).join("selected-python.json");
    std::fs::write(selected, b"{\"path\":\"C:/missing/python.exe\"}").unwrap();
    assert!(environments::selected(&root).is_err());
    environments::clear(&root).unwrap();
    println!("Existing Python validated; workspace became healthy on port {port}; owned backend stopped.");
}
