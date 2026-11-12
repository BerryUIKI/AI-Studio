//! Port conflict detection and Berry instance identification (L03).

use std::net::TcpListener;

#[derive(Debug, PartialEq, Eq)]
pub enum PortStatus {
    Free,
    OccupiedByBerry,
    OccupiedByNonBerry,
}

/// Check the status of a local port (e.g. 8000).
pub fn check_port_status(port: u16) -> PortStatus {
    // Attempt to bind to 127.0.0.1:{port}
    match TcpListener::bind(("127.0.0.1", port)) {
        Ok(_) => PortStatus::Free,
        Err(_) => {
            // Port is in use: probe if it's Berry AI Studio
            if is_berry_health_endpoint(port) {
                PortStatus::OccupiedByBerry
            } else {
                PortStatus::OccupiedByNonBerry
            }
        }
    }
}

/// Probe whether http://127.0.0.1:{port}/health responds with Berry signature.
pub fn is_berry_health_endpoint(port: u16) -> bool {
    berry_runtime::is_backend_healthy(port)
}
