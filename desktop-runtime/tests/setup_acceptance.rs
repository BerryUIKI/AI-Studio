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
