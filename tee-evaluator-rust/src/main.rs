mod attestation;
mod audit;
mod crypto;
mod data;
mod fixed;
mod model;
mod utility;

use anyhow::{Context, Result};
use attestation::{mock::MockAttestation, AttestationProvider};
use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};
use data::read_canonical;
use model::Model;
use utility::{evaluate, UtilityPolicy};

#[derive(Parser)]
struct Cli { #[command(subcommand)] command: Command }

#[derive(Subcommand)]
enum Command {
    Evaluate {
        #[arg(long)] seller: PathBuf,
        #[arg(long)] seller_rows: usize,
        #[arg(long)] validation: PathBuf,
        #[arg(long)] validation_rows: usize,
        #[arg(long)] model: PathBuf,
        #[arg(long)] policy: PathBuf,
        #[arg(long)] seed_hex: String,
        #[arg(long)] output: PathBuf,
    },
    Evidence { #[arg(long)] report_data_hex: String },
}

#[derive(Serialize, Deserialize)]
struct EvaluationReport {
    version: u32,
    metrics: utility::UtilityMetrics,
    development_attestation: bool,
    note: String,
}

fn decode32(value: &str) -> Result<[u8;32]> {
    if value.len() != 64 { anyhow::bail!("seed must be 32-byte hex") }
    let mut out = [0_u8;32];
    for i in 0..32 { out[i] = u8::from_str_radix(&value[2*i..2*i+2],16)?; }
    Ok(out)
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Evaluate { seller, seller_rows, validation, validation_rows, model, policy, seed_hex, output } => {
            let seller = read_canonical(&seller, seller_rows)?;
            let validation = read_canonical(&validation, validation_rows)?;
            let model: Model = serde_json::from_slice(&fs::read(model).context("read model")?)?;
            let policy: UtilityPolicy = serde_json::from_slice(&fs::read(policy).context("read utility policy")?)?;
            let seed = decode32(&seed_hex)?;
            let metrics = evaluate(&model, &seller, &validation, &policy, &seed)?;
            let report = EvaluationReport {
                version: 1, metrics, development_attestation: true,
                note: "Mock backend: correct functional output, no hardware confidentiality".to_owned(),
            };
            fs::write(&output, serde_json::to_string_pretty(&report)?)?;
        }
        Command::Evidence { report_data_hex } => {
            if report_data_hex.len() != 128 { anyhow::bail!("report_data must be 64-byte hex") }
            let mut data = [0_u8;64];
            for i in 0..64 { data[i] = u8::from_str_radix(&report_data_hex[2*i..2*i+2],16)?; }
            let evidence = MockAttestation.evidence(&data)?;
            println!("{}", serde_json::to_string_pretty(&evidence)?);
        }
    }
    Ok(())
}
