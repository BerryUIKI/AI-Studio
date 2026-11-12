//! Measured transfer counters, independent of translated presentation text.
#[derive(Debug, PartialEq)]
pub struct SetupProgress {
    pub stage: String,
    pub downloaded_bytes: Option<u64>,
    pub total_bytes: Option<u64>,
}

impl SetupProgress {
    pub fn stage(stage: &str) -> Self {
        Self {
            stage: stage.into(),
            downloaded_bytes: None,
            total_bytes: None,
        }
    }

    pub fn from_value(value: &serde_json::Value) -> Option<Self> {
        let stage = value["stage"].as_str()?;
        if !["downloading", "verifying", "installing", "validating"].contains(&stage) {
            return None;
        }
        let mut progress = Self::stage(stage);
        if stage == "downloading" {
            progress.downloaded_bytes = value["downloaded_bytes"].as_u64();
            progress.total_bytes = value["total_bytes"].as_u64().filter(|total| {
                *total > 0
                    && progress
                        .downloaded_bytes
                        .is_some_and(|received| received <= *total)
            });
        }
        Some(progress)
    }
}

#[cfg(test)]
mod tests {
    use super::SetupProgress;
    use serde_json::json;

    #[test]
    fn preserves_observed_bytes_and_known_totals() {
        let progress = SetupProgress::from_value(
            &json!({"stage":"downloading","downloaded_bytes":25,"total_bytes":100}),
        )
        .unwrap();
        assert_eq!(progress.downloaded_bytes, Some(25));
        assert_eq!(progress.total_bytes, Some(100));
    }

    #[test]
    fn missing_invalid_or_exceeded_totals_do_not_invent_a_percentage() {
        for total in [json!(null), json!(0), json!(-1), json!("100"), json!(10)] {
            let progress = SetupProgress::from_value(
                &json!({"stage":"downloading","downloaded_bytes":25,"total_bytes":total}),
            )
            .unwrap();
            assert_eq!(progress.downloaded_bytes, Some(25));
            assert_eq!(progress.total_bytes, None);
        }
    }

    #[test]
    fn changing_stage_discards_transfer_counters() {
        let progress = SetupProgress::from_value(
            &json!({"stage":"installing","downloaded_bytes":100,"total_bytes":100}),
        )
        .unwrap();
        assert_eq!(progress, SetupProgress::stage("installing"));
        assert!(SetupProgress::from_value(&json!({"stage":"failed_network"})).is_none());
    }
}
