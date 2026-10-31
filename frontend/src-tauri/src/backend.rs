//! Desktop backend lifecycle uses the shared, ownership-aware runtime.
pub use berry_runtime::{
    log_msg, shutdown_backend, spawn_backend, wait_for_backend_ready, ShutdownMode, ShutdownResult,
};
