//! Structured setup failures: UI recovery never infers causes from English logs.
#[derive(Debug)]
pub struct SetupError {
    pub code: &'static str,
    pub detail: String,
    pub available_bytes: Option<u64>,
    pub required_bytes: Option<u64>,
    pub volume: String,
}

impl SetupError {
    pub fn new(code: &'static str, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
            available_bytes: None,
            required_bytes: None,
            volume: String::new(),
        }
    }
}
impl From<&str> for SetupError {
    fn from(detail: &str) -> Self {
        Self::new("unknown", detail)
    }
}
impl From<String> for SetupError {
    fn from(detail: String) -> Self {
        Self::new("unknown", detail)
    }
}
impl std::fmt::Display for SetupError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.detail.fmt(formatter)
    }
}
impl SetupError {
    pub fn contains(&self, value: &str) -> bool {
        self.detail.contains(value)
    }
}

pub const REQUIRED_BYTES: u64 = 1024 * 1024 * 1024;

pub fn check_space(available: u64, volume: String) -> Result<(), SetupError> {
    if available >= REQUIRED_BYTES {
        return Ok(());
    }
    Err(SetupError {
        code: "disk_space",
        detail: "Insufficient free space on the installation volume".into(),
        available_bytes: Some(available),
        required_bytes: Some(REQUIRED_BYTES),
        volume,
    })
}

pub fn volume(path: &std::path::Path) -> String {
    path.components()
        .next()
        .map(|part| part.as_os_str().to_string_lossy().into_owned())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    #[test]
    fn free_space_is_measured_against_the_installation_requirement() {
        let error = super::check_space(super::REQUIRED_BYTES - 1, "D:".into()).unwrap_err();
        assert_eq!(error.code, "disk_space");
        assert_eq!(error.volume, "D:");
        assert_eq!(error.required_bytes, Some(super::REQUIRED_BYTES));
        assert!(super::check_space(super::REQUIRED_BYTES, "C:".into()).is_ok());
    }
}
