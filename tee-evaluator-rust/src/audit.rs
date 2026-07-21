use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use crate::{data::{Row, FEATURES}, fixed::Fixed};

#[derive(Clone, Debug)]
pub struct AuditProbe {
    pub weights: [Fixed; FEATURES],
    pub bias: Fixed,
    pub center: [Fixed; FEATURES],
    pub inv_scale_sq: [Fixed; FEATURES],
    pub margin_threshold: Fixed,
    pub distance_threshold: Fixed,
    pub missing_threshold: u16,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AuditScore {
    pub margin: Fixed,
    pub distance: Fixed,
    pub missing_count: u16,
    pub failed: bool,
}

pub fn score(row: &Row, probe: &AuditProbe) -> Result<AuditScore> {
    if !row.valid { bail!("padding row is not a semantic sample") }
    let mut linear = probe.bias;
    let mut distance = Fixed::ZERO;
    let mut missing = 0_u16;
    for k in 0..FEATURES {
        if row.missing_mask[k/8] & (1 << (k%8)) != 0 {
            missing += 1;
            continue;
        }
        linear = linear.checked_add(probe.weights[k].checked_mul(row.features[k])?)?;
        let delta = row.features[k].checked_sub(probe.center[k])?;
        distance = distance.checked_add(delta.checked_mul(delta)?.checked_mul(probe.inv_scale_sq[k])?)?;
    }
    let margin = if row.label == 1 { linear } else { Fixed(-linear.0) };
    let failed = margin.0 < probe.margin_threshold.0 || distance.0 > probe.distance_threshold.0 || missing > probe.missing_threshold;
    Ok(AuditScore { margin, distance, missing_count: missing, failed })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_probe() -> AuditProbe {
        AuditProbe {
            weights: [Fixed::ZERO; FEATURES],
            bias: Fixed::ZERO,
            center: [Fixed::ZERO; FEATURES],
            inv_scale_sq: [Fixed::ZERO; FEATURES],
            margin_threshold: Fixed::from_f64(-100.0).unwrap(),
            distance_threshold: Fixed::from_f64(1000.0).unwrap(),
            missing_threshold: 16,
        }
    }

    #[test]
    fn audit_all_pass_with_clean_data() {
        let probe = dummy_probe();
        let row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        let s = score(&row, &probe).unwrap();
        assert!(!s.failed, "clean row with lenient probe should pass");
    }

    #[test]
    fn audit_fail_on_margin() {
        let mut probe = dummy_probe();
        probe.margin_threshold = Fixed::from_f64(100.0).unwrap();
        // Zero features, zero bias -> margin = 0.
        // margin_threshold = 100 means margin 0 < 100 -> fail.
        let row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        let s = score(&row, &probe).unwrap();
        assert!(s.failed, "should fail on margin");
    }

    #[test]
    fn audit_fail_on_missing() {
        let mut probe = dummy_probe();
        probe.missing_threshold = 5;
        let row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0xFF; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        // All 128 features are marked missing.
        let s = score(&row, &probe).unwrap();
        assert!(s.failed, "should fail on missing count");
        assert_eq!(s.missing_count, 128);
    }

    #[test]
    fn audit_padding_row_rejected() {
        let probe = dummy_probe();
        let row = Row {
            row_id: 0,
            valid: false,
            label: 0,
            timestamp: 0,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        assert!(score(&row, &probe).is_err());
    }
}
