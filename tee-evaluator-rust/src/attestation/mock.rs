use anyhow::Result;
use blake3::hash;
use super::{AttestationProvider, Evidence};

pub struct MockAttestation;
impl AttestationProvider for MockAttestation {
    fn evidence(&self, report_data: &[u8;64]) -> Result<Evidence> {
        Ok(Evidence {
            backend: "mock".to_owned(),
            measurement: hash(b"DDTM_QAS_MOCK_IMAGE_V1").to_hex().to_string(),
            report_data_hex: hex(report_data),
            raw_evidence_b64: String::new(),
            development_only: true,
        })
    }
}
fn hex(data: &[u8]) -> String { data.iter().map(|b| format!("{b:02x}")).collect() }
