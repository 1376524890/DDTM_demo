use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Evidence {
    pub backend: String,
    pub measurement: String,
    pub report_data_hex: String,
    pub raw_evidence_b64: String,
    pub development_only: bool,
}

pub trait AttestationProvider: Send + Sync {
    fn evidence(&self, report_data: &[u8;64]) -> Result<Evidence>;
}

pub mod mock;
