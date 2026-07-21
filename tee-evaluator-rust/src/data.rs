use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::{fs::File, io::{BufReader, Read}, path::Path};
use crate::fixed::Fixed;

pub const FEATURES: usize = 128;
pub const ROW_BYTES: usize = 548;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Row {
    pub row_id: u64,
    pub valid: bool,
    pub label: i8,
    pub timestamp: u64,
    pub missing_mask: [u8; 16],
    pub features: [Fixed; FEATURES],
}

pub fn read_canonical(path: &Path, row_count: usize) -> Result<Vec<Row>> {
    if row_count > 100_000 { bail!("row_count exceeds policy") }
    let mut reader = BufReader::new(File::open(path).context("open canonical dataset")?);
    let mut rows = Vec::with_capacity(row_count);
    let mut raw = [0_u8; ROW_BYTES];
    for expected in 0..row_count {
        reader.read_exact(&mut raw).with_context(|| format!("read row {expected}"))?;
        let version = u16::from_le_bytes(raw[0..2].try_into().unwrap());
        if version != 1 { bail!("unsupported row version {version}") }
        let row_id = u64::from_le_bytes(raw[2..10].try_into().unwrap());
        if row_id != expected as u64 { bail!("non-canonical row id") }
        let valid = raw[10] == 1;
        let label = raw[11] as i8;
        if valid && label != -1 && label != 1 { bail!("invalid label") }
        let timestamp = u64::from_le_bytes(raw[12..20].try_into().unwrap());
        let missing_mask: [u8;16] = raw[20..36].try_into().unwrap();
        let mut features = [Fixed::ZERO; FEATURES];
        let mut off = 36;
        for item in &mut features {
            *item = Fixed(i32::from_le_bytes(raw[off..off+4].try_into().unwrap()) as i64);
            off += 4;
        }
        rows.push(Row { row_id, valid, label, timestamp, missing_mask, features });
    }
    let mut trailing = [0u8;1];
    if reader.read(&mut trailing)? != 0 { bail!("canonical file contains uncommitted trailing bytes") }
    Ok(rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn write_test_canonical(rows: &[Row]) -> Vec<u8> {
        let mut buf = Vec::new();
        for row in rows {
            let mut raw = [0u8; ROW_BYTES];
            raw[0..2].copy_from_slice(&1u16.to_le_bytes());
            raw[2..10].copy_from_slice(&row.row_id.to_le_bytes());
            raw[10] = if row.valid { 1 } else { 0 };
            raw[11] = row.label as u8;
            raw[12..20].copy_from_slice(&row.timestamp.to_le_bytes());
            raw[20..36].copy_from_slice(&row.missing_mask);
            let mut off = 36;
            for f in &row.features {
                raw[off..off+4].copy_from_slice(&(f.0 as i32).to_le_bytes());
                off += 4;
            }
            buf.write_all(&raw).unwrap();
        }
        buf
    }

    #[test]
    fn read_round_trip() {
        let rows = vec![Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        }];
        let buf = write_test_canonical(&rows);
        let tmp = std::env::temp_dir().join("ddtm_test_canonical.bin");
        std::fs::write(&tmp, &buf).unwrap();
        let read = read_canonical(&tmp, rows.len()).unwrap();
        assert_eq!(read[0].row_id, rows[0].row_id);
        assert_eq!(read[0].valid, rows[0].valid);
        assert_eq!(read[0].label, rows[0].label);
        let _ = std::fs::remove_file(&tmp);
    }

    #[test]
    fn read_rejects_bad_version() {
        let mut buf = vec![0u8; ROW_BYTES];
        buf[0] = 2; // Wrong version
        let tmp = std::env::temp_dir().join("ddtm_test_bad.bin");
        std::fs::write(&tmp, &buf).unwrap();
        assert!(read_canonical(&tmp, 1).is_err());
        let _ = std::fs::remove_file(&tmp);
    }

    #[test]
    fn read_rejects_bad_row_id() {
        let mut buf = vec![0u8; ROW_BYTES];
        buf[0] = 1; // version ok
        buf[2] = 99; // row_id != expected 0
        let tmp = std::env::temp_dir().join("ddtm_test_badid.bin");
        std::fs::write(&tmp, &buf).unwrap();
        assert!(read_canonical(&tmp, 1).is_err());
        let _ = std::fs::remove_file(&tmp);
    }

    #[test]
    fn read_rejects_excess_rows() {
        assert!(read_canonical(&std::path::PathBuf::from("/nonexistent"), 100001).is_err());
    }

    #[test]
    fn read_rejects_trailing_bytes() {
        let rows = vec![Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        }];
        let mut buf = write_test_canonical(&rows);
        buf.push(0x00); // trailing byte
        let tmp = std::env::temp_dir().join("ddtm_test_trail.bin");
        std::fs::write(&tmp, &buf).unwrap();
        assert!(read_canonical(&tmp, 1).is_err());
        let _ = std::fs::remove_file(&tmp);
    }
}
