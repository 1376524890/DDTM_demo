//! verify-vectors：DDTM-CANONICAL-V1 数据层的 Rust 重新实现。
//!
//! 读取 G1 清单，用从零编写的 Poseidon2 width-4 置换（常量钉定为 gnark-crypto
//! v0.20.1）在原始 crypto-bigint U256 域算术（split_mul + 宽余数）上独立重新推导
//! 每一行叶子与 Merkle 根。之所以避开 Montgomery 形式，是因为 crypto-bigint 0.6.1
//! 的 MontyForm 自乘存在别名缺陷。

use crypto_bigint::{Encoding, NonZero, U256};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{fs, path::PathBuf, sync::OnceLock};

type Fe = U256; // 已取模的规范域元素

const ROW_SIZE: usize = 548;
const FEATURE_COUNT: usize = 128;
const MASK_SIZE: usize = 16;
const LOWER_Q16: i32 = i32::MIN;
const UPPER_Q16: i32 = i32::MAX;

// 域模数从钉定的 poseidon 参数文件一次性加载（唯一真相来源——切勿硬编码，
// BN254 标量域常量很容易抄错）。
static MODULUS: OnceLock<U256> = OnceLock::new();

fn modulus() -> U256 {
    *MODULUS.get().expect("modulus not loaded")
}

fn nz() -> NonZero<U256> {
    NonZero::new(modulus()).unwrap()
}

// ---------------------------------------------------------------------------
// 域运算辅助（原始 U256 算术）
// ---------------------------------------------------------------------------

fn fe_add(a: &Fe, b: &Fe) -> Fe {
    a.wrapping_add(b).rem(&nz())
}
fn fe_mul(a: &Fe, b: &Fe) -> Fe {
    a.mul_mod_vartime(b, &nz())
}
fn fe_square(a: &Fe) -> Fe {
    fe_mul(a, a)
}

/// 把 0x 前缀的十六进制整数解析为已取模的域元素。
fn fe_from_hex(s: &str) -> Fe {
    let h = s.trim_start_matches("0x");
    let padded = format!("{h:0>64}");
    let u = U256::from_be_hex(&padded);
    u.rem(&nz())
}

fn fe_from_be_bytes(b: [u8; 32]) -> Fe {
    U256::from_be_bytes(b).rem(&nz())
}

fn fe_from_le_bytes(b: &[u8]) -> Fe {
    // 把 b 解释为小端整数：反转后右对齐放进 32 字节缓冲（使自然的 MSB 落在正确的
    // 256 的幂次上）。
    let n = b.len();
    let mut padded = [0u8; 32];
    for i in 0..n {
        padded[32 - n + i] = b[n - 1 - i];
    }
    U256::from_be_bytes(padded).rem(&nz())
}

fn fe_to_hex(e: &Fe) -> String {
    let bytes = e.to_be_bytes();
    let mut start = 0;
    while start < 31 && bytes[start] == 0 {
        start += 1;
    }
    let mut s = String::from("0x");
    for &b in &bytes[start..] {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

fn hex_eq(a: &str, b: &str) -> bool {
    let na = a.trim_start_matches("0x").trim_start_matches('0');
    let nb = b.trim_start_matches("0x").trim_start_matches('0');
    na == nb || (na.is_empty() && nb.is_empty())
}

// ---------------------------------------------------------------------------
// Poseidon2 width-4 置换 + sponge
// ---------------------------------------------------------------------------

struct Poseidon {
    diag: [Fe; 4],
    round_keys: Vec<[Fe; 4]>,
    full_rounds: usize,
    partial_rounds: usize,
}

impl Poseidon {
    fn load(path: &str) -> anyhow::Result<Poseidon> {
        let raw = fs::read_to_string(path)?;
        let v: Value = serde_json::from_str(&raw)?;

        // 从钉定参数初始化域模数（与 Python/Go/gnark 共享的唯一真相来源）。
        let modulus_hex = v["modulus"].as_str().unwrap().trim_start_matches("0x");
        let _ = MODULUS.set(U256::from_be_hex(&format!("{modulus_hex:0>64}")));

        let diag = parse_fe_array(&v["diag_m1"]);
        let mut round_keys = Vec::new();
        for rnd in v["round_keys"].as_array().unwrap() {
            round_keys.push(parse_fe_array(rnd));
        }
        let full = v["full_rounds"].as_u64().unwrap() as usize;
        let partial = v["partial_rounds"].as_u64().unwrap() as usize;
        let p = Poseidon { diag, round_keys, full_rounds: full, partial_rounds: partial };

        // KAT 自检。
        for k in v["kat"].as_array().unwrap() {
            let inp: Vec<String> = k["input"].as_array().unwrap()
                .iter().map(|x| x.as_str().unwrap().to_string()).collect();
            let out: Vec<String> = k["output"].as_array().unwrap()
                .iter().map(|x| x.as_str().unwrap().to_string()).collect();
            let mut s = [fe_from_hex(&inp[0]), fe_from_hex(&inp[1]),
                         fe_from_hex(&inp[2]), fe_from_hex(&inp[3])];
            p.permute(&mut s);
            for i in 0..4 {
                if !hex_eq(&fe_to_hex(&s[i]), &out[i]) {
                    eprintln!("KAT elt {i}: got {} want {}", fe_to_hex(&s[i]), out[i]);
                    anyhow::bail!("poseidon KAT mismatch");
                }
            }
        }
        Ok(p)
    }

    fn permute(&self, s: &mut [Fe; 4]) {
        external(s);
        let hf = self.full_rounds / 2;
        for i in 0..hf {
            add_round_key(&self.round_keys[i], s);
            for j in 0..4 { sbox(&mut s[j]); }
            external(s);
        }
        for i in hf..hf + self.partial_rounds {
            s[0] = fe_add(&s[0], &self.round_keys[i][0]);
            sbox(&mut s[0]);
            internal(&self.diag, s);
        }
        for i in hf + self.partial_rounds..self.full_rounds + self.partial_rounds {
            add_round_key(&self.round_keys[i], s);
            for j in 0..4 { sbox(&mut s[j]); }
            external(s);
        }
    }

    /// H_P(tag, elements)：width-4 置换之上的 rate-3 sponge。
    fn hash(&self, tag: &Fe, elements: &[Fe]) -> Fe {
        let mut msg: Vec<Fe> = Vec::with_capacity(2 + elements.len());
        msg.push(*tag);
        msg.push(U256::from_u64(elements.len() as u64));
        msg.extend_from_slice(elements);
        let mut state = [U256::ZERO, U256::ZERO, U256::ZERO, U256::ZERO];
        let mut idx = 0;
        while idx < msg.len() {
            let end = (idx + 3).min(msg.len());
            for j in idx..end {
                state[j - idx] = fe_add(&state[j - idx], &msg[j]);
            }
            self.permute(&mut state);
            idx += 3;
        }
        state[0]
    }
}

fn sbox(x: &mut Fe) {
    let x2 = fe_square(x);
    let x4 = fe_square(&x2);
    *x = fe_mul(&x4, x);
}

fn external(s: &mut [Fe; 4]) {
    let t0 = fe_add(&s[0], &s[1]);
    let t1 = fe_add(&s[2], &s[3]);
    let s1d = fe_add(&s[1], &s[1]);
    let s3d = fe_add(&s[3], &s[3]);
    let t2 = fe_add(&t1, &s1d);
    let t3 = fe_add(&t0, &s3d);
    let t1q = fe_add(&fe_add(&t1, &t1), &fe_add(&t1, &t1));
    let t0q = fe_add(&fe_add(&t0, &t0), &fe_add(&t0, &t0));
    let t4 = fe_add(&t1q, &t3);
    let t5 = fe_add(&t0q, &t2);
    s[0] = fe_add(&t3, &t5);
    s[1] = t5;
    s[2] = fe_add(&t2, &t4);
    s[3] = t4;
}

fn internal(diag: &[Fe; 4], s: &mut [Fe; 4]) {
    let mut tot = fe_add(&s[0], &s[1]);
    tot = fe_add(&tot, &s[2]);
    tot = fe_add(&tot, &s[3]);
    for i in 0..4 {
        s[i] = fe_add(&fe_mul(&s[i], &diag[i]), &tot);
    }
}

fn add_round_key(rk: &[Fe; 4], s: &mut [Fe; 4]) {
    for i in 0..4 {
        s[i] = fe_add(&s[i], &rk[i]);
    }
}

fn parse_fe_array(v: &Value) -> [Fe; 4] {
    let arr = v.as_array().unwrap();
    [fe_from_hex(arr[0].as_str().unwrap()), fe_from_hex(arr[1].as_str().unwrap()),
     fe_from_hex(arr[2].as_str().unwrap()), fe_from_hex(arr[3].as_str().unwrap())]
}

// ---------------------------------------------------------------------------
// 量化：IEEE-754 f32 -> Q16.16
// ---------------------------------------------------------------------------

const ERR_NON_FINITE: &str = "NON_FINITE_FEATURE";

fn quantize(value: f32) -> Result<i32, String> {
    let bits = value.to_bits();
    let sign = (bits >> 31) & 1;
    let exponent = (bits >> 23) & 0xff;
    let fraction = bits & 0x7fffff;
    if exponent == 0xff {
        return Err(ERR_NON_FINITE.to_string());
    }
    let (mantissa, shift) = if exponent == 0 {
        (fraction as i64, -149 + 16)
    } else {
        (((1u32 << 23) | fraction) as i64, exponent as i32 - 150 + 16)
    };
    let signed = if sign == 1 { -mantissa } else { mantissa };
    let q = if shift >= 0 {
        signed << shift
    } else {
        round_div_pow2_even(signed as i128, (-shift) as u32) as i64
    };
    let mut q = q as i32;
    if q < LOWER_Q16 { q = LOWER_Q16; }
    if q > UPPER_Q16 { q = UPPER_Q16; }
    Ok(q)
}

fn round_div_pow2_even(numerator: i128, shift: u32) -> i128 {
    let negative = numerator < 0;
    let magnitude = numerator.unsigned_abs();
    let denominator = 1u128 << shift;
    let quotient = magnitude / denominator;
    let remainder = magnitude % denominator;
    let half = denominator >> 1;
    let mut q = quotient;
    if remainder > half { q += 1; }
    else if remainder == half && q % 2 == 1 { q += 1; }
    if negative { -(q as i128) } else { q as i128 }
}

// ---------------------------------------------------------------------------
// 行编解码（548 字节，小端）
// ---------------------------------------------------------------------------

struct Row {
    row_id: u64, timestamp: u64, features: [i32; FEATURE_COUNT],
    mask: [u8; MASK_SIZE], label: i8, valid: u8,
}

impl Row {
    fn encode(&self) -> Vec<u8> {
        let mut out = vec![0u8; ROW_SIZE];
        out[0..8].copy_from_slice(&self.row_id.to_le_bytes());
        out[8..16].copy_from_slice(&self.timestamp.to_le_bytes());
        for (i, f) in self.features.iter().enumerate() {
            out[16 + i * 4..20 + i * 4].copy_from_slice(&f.to_le_bytes());
        }
        out[528..544].copy_from_slice(&self.mask);
        out[544] = self.label as u8;
        out[545] = self.valid;
        out
    }
}

fn pack_row_fields(blob: &[u8]) -> Vec<Fe> {
    let mut out = Vec::with_capacity(18);
    let mut offset = 0;
    while offset < ROW_SIZE {
        let end = (offset + 31).min(ROW_SIZE);
        out.push(fe_from_le_bytes(&blob[offset..end]));
        offset += 31;
    }
    out
}

// ---------------------------------------------------------------------------
// Schema + 域标签 + Merkle
// ---------------------------------------------------------------------------

struct Context {
    p: Poseidon,
    schema_hi: Fe, schema_lo: Fe,
    tag_row: Fe, tag_padding: Fe, tag_node: Fe,
}

fn sha256_bytes(data: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(data);
    h.finalize().into()
}

fn be16(b: &[u8]) -> [u8; 32] {
    let mut padded = [0u8; 32];
    padded[16..].copy_from_slice(b);
    padded
}

fn schema_halves(path: &str) -> anyhow::Result<(Fe, Fe)> {
    let raw = fs::read(path)?;
    let digest = sha256_bytes(&raw);
    Ok((fe_from_be_bytes(be16(&digest[..16])), fe_from_be_bytes(be16(&digest[16..]))))
}

fn domain_tag(name: &str) -> Fe {
    fe_from_be_bytes(sha256_bytes(name.as_bytes()))
}

fn row_leaf(ctx: &Context, index: u64, blob: &[u8]) -> Fe {
    let mut elems = vec![ctx.schema_hi, ctx.schema_lo];
    elems.push(U256::from_u64(index));
    elems.extend(pack_row_fields(blob));
    ctx.p.hash(&ctx.tag_row, &elems)
}

fn padding_leaf(ctx: &Context, index: u64) -> Fe {
    let elems = vec![ctx.schema_hi, ctx.schema_lo, U256::from_u64(index)];
    ctx.p.hash(&ctx.tag_padding, &elems)
}

fn node_hash(ctx: &Context, level: u64, left: &Fe, right: &Fe) -> Fe {
    let elems = vec![U256::from_u64(level), *left, *right];
    ctx.p.hash(&ctx.tag_node, &elems)
}

fn build_root(ctx: &Context, blobs: &[Vec<u8>], capacity: usize) -> Fe {
    let mut leaves: Vec<Fe> = Vec::with_capacity(capacity);
    for (i, b) in blobs.iter().enumerate() {
        leaves.push(row_leaf(ctx, i as u64, b));
    }
    for i in blobs.len()..capacity {
        leaves.push(padding_leaf(ctx, i as u64));
    }
    let mut level = 0u64;
    while leaves.len() > 1 {
        let mut next = Vec::with_capacity(leaves.len() / 2);
        for c in leaves.chunks(2) {
            next.push(node_hash(ctx, level, &c[0], &c[1]));
        }
        leaves = next;
        level += 1;
    }
    leaves[0]
}

fn generated_features(i: i64) -> [i32; FEATURE_COUNT] {
    let mut out = [0i32; FEATURE_COUNT];
    for j in 0..FEATURE_COUNT {
        out[j] = (((i + 1) * (j as i64 + 1)) & 0xffff) as i32;
    }
    out
}

fn encode_generated_row(i: i64) -> Vec<u8> {
    let label: i8 = if i % 2 == 0 { 1 } else { -1 };
    Row {
        row_id: i as u64, timestamp: (1700000000 + i) as u64,
        features: generated_features(i), mask: [0u8; MASK_SIZE], label, valid: 1,
    }.encode()
}

// ---------------------------------------------------------------------------
// 清单校验
// ---------------------------------------------------------------------------

#[derive(serde::Serialize)]
struct CaseResult {
    id: String, kind: String, status: String,
    #[serde(skip_serializing_if = "Option::is_none")] expected_root: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")] actual_root: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")] expected_error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")] actual_error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")] note: Option<String>,
}

fn main() -> anyhow::Result<()> {
    let root = repo_root();
    let manifest_path = root.join("experiments/vectors/manifest.json");
    let out_path = root.join("experiments/raw/g1-rust.json");
    let schema_path = root.join("specs/canonical-data-v1.schema.json");
    let poseidon_path = root.join("specs/poseidon2-bn254-v1.json");

    let p = Poseidon::load(poseidon_path.to_str().unwrap())?;
    let (schema_hi, schema_lo) = schema_halves(schema_path.to_str().unwrap())?;
    let ctx = Context {
        p, schema_hi, schema_lo,
        tag_row: domain_tag("DDTM_ROW_V1"),
        tag_padding: domain_tag("DDTM_PADDING_V1"),
        tag_node: domain_tag("DDTM_NODE_V1"),
    };

    let manifest: Value = serde_json::from_str(&fs::read_to_string(&manifest_path)?)?;
    let cases = manifest["cases"].as_array().unwrap();
    let mut results = Vec::new();
    let mut passed = 0usize;
    let mut failed = 0usize;
    for case in cases {
        let id = case["id"].as_str().unwrap().to_string();
        let kind = case["kind"].as_str().unwrap().to_string();
        let res = match kind.as_str() {
            "positive" => verify_positive(&ctx, case, &manifest_path, &id),
            "negative" => verify_negative(case, &manifest_path, &id),
            "generated" => verify_generated(&ctx, case, &id),
            _ => CaseResult {
                id, kind, status: "FAIL".into(), expected_root: None, actual_root: None,
                expected_error: None, actual_error: None, note: Some("unknown kind".into()),
            },
        };
        if res.status == "PASS" { passed += 1; } else { failed += 1; }
        results.push(res);
    }

    let out = serde_json::json!({
        "implementation": "rust",
        "schema_sha256": manifest["schema_sha256"],
        "cases": results,
        "summary": {"passed": passed, "failed": failed},
    });
    fs::create_dir_all(out_path.parent().unwrap())?;
    fs::write(&out_path, serde_json::to_string_pretty(&out).unwrap())?;
    println!("rust verify-vectors: {} passed, {} failed -> {}", passed, failed, out_path.display());
    if failed > 0 { std::process::exit(1); }
    Ok(())
}

fn verify_positive(ctx: &Context, case: &Value, manifest_path: &PathBuf, id: &str) -> CaseResult {
    let vectors_dir = manifest_path.parent().unwrap();
    let blob = match fs::read(vectors_dir.join(case["blob"].as_str().unwrap())) {
        Ok(b) => b,
        Err(e) => return fail(id, "positive", &format!("read blob: {e}")),
    };
    if sha256_hex(&blob) != case["blob_sha256"].as_str().unwrap() {
        return fail(id, "positive", "blob sha256 mismatch");
    }
    let row_count = blob.len() / ROW_SIZE;
    let mut blobs: Vec<Vec<u8>> = Vec::new();
    let mut leaves: Vec<String> = Vec::new();
    for i in 0..row_count {
        let rb = &blob[i * ROW_SIZE..(i + 1) * ROW_SIZE];
        leaves.push(fe_to_hex(&row_leaf(ctx, i as u64, rb)));
        blobs.push(rb.to_vec());
    }
    let exp_leaves = case["expected_row_leaves"].as_array().unwrap();
    for (i, want) in exp_leaves.iter().enumerate() {
        if !hex_eq(&leaves[i], want.as_str().unwrap()) {
            return fail(id, "positive", &format!("leaf {i} mismatch"));
        }
    }
    let capacity = case["capacity"].as_u64().unwrap() as usize;
    let root = build_root(ctx, &blobs, capacity);
    let got = fe_to_hex(&root);
    let expected = case["expected_data_root"].as_str().unwrap();
    let pass = hex_eq(&got, expected);
    CaseResult {
        id: id.into(), kind: "positive".into(),
        status: if pass { "PASS".into() } else { "FAIL".into() },
        expected_root: Some(expected.into()), actual_root: Some(got),
        expected_error: None, actual_error: None,
        note: if pass { None } else { Some("root mismatch".into()) },
    }
}

fn verify_negative(case: &Value, manifest_path: &PathBuf, id: &str) -> CaseResult {
    let vectors_dir = manifest_path.parent().unwrap();
    let raw = fs::read_to_string(vectors_dir.join(case["input"].as_str().unwrap())).unwrap();
    let def: Value = serde_json::from_str(&raw).unwrap();
    let sentinel = def["row"]["feature_sentinel"].as_str().unwrap();
    let value = match sentinel {
        "NaN" => f32::NAN, "+Inf" => f32::INFINITY, "-Inf" => f32::NEG_INFINITY, _ => 0.0,
    };
    let expected = case["expected_error"].as_str().unwrap();
    match quantize(value) {
        Ok(_) => CaseResult {
            id: id.into(), kind: "negative".into(), status: "FAIL".into(),
            expected_root: None, actual_root: None,
            expected_error: Some(expected.into()), actual_error: None,
            note: Some("expected rejection".into()),
        },
        Err(code) => CaseResult {
            id: id.into(), kind: "negative".into(),
            status: if code == expected { "PASS".into() } else { "FAIL".into() },
            expected_root: None, actual_root: None,
            expected_error: Some(expected.into()), actual_error: Some(code), note: None,
        },
    }
}

fn verify_generated(ctx: &Context, case: &Value, id: &str) -> CaseResult {
    if case["generator"].as_str().unwrap() != "synthetic-v1" {
        return fail(id, "generated", "unknown generator");
    }
    let row_count = case["row_count"].as_u64().unwrap() as i64;
    let capacity = case["capacity"].as_u64().unwrap() as usize;
    let blobs: Vec<Vec<u8>> = (0..row_count).map(encode_generated_row).collect();
    let root = build_root(ctx, &blobs, capacity);
    let got = fe_to_hex(&root);
    let expected = case["expected_data_root"].as_str().unwrap();
    let pass = hex_eq(&got, expected);
    CaseResult {
        id: id.into(), kind: "generated".into(),
        status: if pass { "PASS".into() } else { "FAIL".into() },
        expected_root: Some(expected.into()), actual_root: Some(got),
        expected_error: None, actual_error: None,
        note: if pass { None } else { Some("root mismatch".into()) },
    }
}

fn fail(id: &str, kind: &str, note: &str) -> CaseResult {
    CaseResult {
        id: id.into(), kind: kind.into(), status: "FAIL".into(),
        expected_root: None, actual_root: None,
        expected_error: None, actual_error: None, note: Some(note.into()),
    }
}

fn sha256_hex(b: &[u8]) -> String {
    let d = sha256_bytes(b);
    let mut s = String::new();
    for byte in d { s.push_str(&format!("{:02x}", byte)); }
    s
}

fn repo_root() -> PathBuf {
    let mut dir = std::env::current_dir().unwrap();
    for _ in 0..8 {
        if dir.join("specs/canonical-data-v1.md").exists() { return dir; }
        if !dir.pop() { break; }
    }
    PathBuf::from(".")
}
