use anyhow::{bail, Result};
use blake3::Hasher;
use serde::{Deserialize, Serialize};
use crate::{data::Row, fixed::Fixed, model::{Gradient, Model}};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct UtilityPolicy {
    pub learning_rate: Fixed,
    pub gradient_clip: Fixed,
    pub delta_clip: Fixed,
    pub mom_groups: usize,
    pub lambda_mad: Fixed,
    pub lambda_shift: Fixed,
    pub lambda_linear: Fixed,
    pub min_utility: Fixed,
    pub max_linear_error: Fixed,
    pub max_shift: Fixed,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct UtilityMetrics {
    pub u_mom: Fixed,
    pub mad: Fixed,
    pub shift: Fixed,
    pub u_first_order: Fixed,
    pub linear_error: Fixed,
    pub u_cert: Fixed,
    pub pass: bool,
}

fn deterministic_group(row_id: u64, seed: &[u8; 32], groups: usize) -> usize {
    let mut h = Hasher::new();
    h.update(b"DDTM_MOM_GROUP_V1"); h.update(seed); h.update(&row_id.to_le_bytes());
    let digest = h.finalize();
    u64::from_le_bytes(digest.as_bytes()[0..8].try_into().unwrap()) as usize % groups
}

fn median(mut values: Vec<Fixed>) -> Result<Fixed> {
    if values.is_empty() { bail!("median of empty set") }
    values.sort_by_key(|v| v.0);
    Ok(values[values.len()/2])
}

fn validation_delta(before: &Model, after: &Model, validation: &[Row], clip: Fixed) -> Result<Vec<Fixed>> {
    validation.iter().filter(|r| r.valid).map(|row| {
        let delta = before.hinge_loss(row)?.checked_sub(after.hinge_loss(row)?)?;
        Ok(delta.clamp(Fixed(-clip.0), clip))
    }).collect()
}

fn mom(values: &[Fixed], validation: &[Row], seed: &[u8;32], groups: usize) -> Result<(Fixed, Fixed)> {
    if groups < 3 || groups % 2 == 0 { bail!("mom_groups must be odd and >=3") }
    let mut sums = vec![0_i128; groups];
    let mut counts = vec![0_i64; groups];
    let mut value_index = 0;
    for row in validation.iter().filter(|r| r.valid) {
        let g = deterministic_group(row.row_id, seed, groups);
        sums[g] += values[value_index].0 as i128;
        counts[g] += 1;
        value_index += 1;
    }
    let mut means = Vec::with_capacity(groups);
    for g in 0..groups {
        if counts[g] == 0 { bail!("empty MoM group") }
        means.push(Fixed((sums[g] / counts[g] as i128) as i64));
    }
    let center = median(means.clone())?;
    let deviations = means.into_iter().map(|v| Fixed(v.0.saturating_sub(center.0).saturating_abs())).collect();
    Ok((center, median(deviations)?))
}

fn mean_gradient_dot(validation_grad: &Gradient, seller_grad: &Gradient) -> Result<Fixed> {
    if validation_grad.samples == 0 || seller_grad.samples == 0 { bail!("empty gradient") }
    let nv = validation_grad.samples as i128;
    let nd = seller_grad.samples as i128;
    let mut sum = 0_i128;
    for j in 0..crate::model::HIDDEN {
        sum += (validation_grad.b1[j] / nv) * (seller_grad.b1[j] / nd);
        sum += (validation_grad.w2[j] / nv) * (seller_grad.w2[j] / nd);
        for k in 0..crate::data::FEATURES { sum += (validation_grad.w1[j][k] / nv) * (seller_grad.w1[j][k] / nd); }
    }
    sum += (validation_grad.b2 / nv) * (seller_grad.b2 / nd);
    let scaled = sum >> 16;
    if scaled < i64::MIN as i128 || scaled > i64::MAX as i128 { bail!("dot overflow") }
    Ok(Fixed(scaled as i64))
}

fn diagonal_shift(seller: &[Row], validation: &[Row]) -> Result<Fixed> {
    // Deterministic, bounded mean-shift proxy. A production policy may replace this
    // with median/MAD statistics while preserving the same report interface.
    let mut total = 0_i128;
    for k in 0..crate::data::FEATURES {
        let ds: Vec<i64> = seller.iter().filter(|r| r.valid && (r.missing_mask[k/8] & (1 << (k%8))) == 0).map(|r| r.features[k].0).collect();
        let dv: Vec<i64> = validation.iter().filter(|r| r.valid && (r.missing_mask[k/8] & (1 << (k%8))) == 0).map(|r| r.features[k].0).collect();
        if ds.is_empty() || dv.is_empty() { continue }
        let ms = ds.iter().map(|x| *x as i128).sum::<i128>() / ds.len() as i128;
        let mv = dv.iter().map(|x| *x as i128).sum::<i128>() / dv.len() as i128;
        total += (ms - mv).abs().min(8_i128 << 16);
    }
    Ok(Fixed((total / crate::data::FEATURES as i128) as i64))
}

pub fn evaluate(model: &Model, seller: &[Row], validation: &[Row], policy: &UtilityPolicy, seed: &[u8;32]) -> Result<UtilityMetrics> {
    model.validate()?;
    let mut gd = Gradient::zero();
    for row in seller { model.accumulate_gradient(row, &mut gd)?; }
    let mut gv = Gradient::zero();
    for row in validation { model.accumulate_gradient(row, &mut gv)?; }
    let updated = model.one_step(&gd, policy.learning_rate, policy.gradient_clip)?;
    let deltas = validation_delta(model, &updated, validation, policy.delta_clip)?;
    let (u_mom, mad) = mom(&deltas, validation, seed, policy.mom_groups)?;
    let raw_dot = mean_gradient_dot(&gv, &gd)?;
    let u_first_order = policy.learning_rate.checked_mul(raw_dot)?;
    let linear_error = u_mom.checked_sub(u_first_order)?.abs();
    let shift = diagonal_shift(seller, validation)?;
    let penalty = policy.lambda_mad.checked_mul(mad)?
        .checked_add(policy.lambda_shift.checked_mul(shift)?)?
        .checked_add(policy.lambda_linear.checked_mul(linear_error)?)?;
    let u_cert = u_mom.checked_sub(penalty)?;
    let pass = u_cert.0 >= policy.min_utility.0 && linear_error.0 <= policy.max_linear_error.0 && shift.0 <= policy.max_shift.0;
    Ok(UtilityMetrics { u_mom, mad, shift, u_first_order, linear_error, u_cert, pass })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::Row;
    use crate::fixed::Fixed;
    use crate::model::Model;

    fn dummy_policy() -> UtilityPolicy {
        UtilityPolicy {
            learning_rate: Fixed::from_f64(0.01).unwrap(),
            gradient_clip: Fixed::from_f64(5.0).unwrap(),
            delta_clip: Fixed::from_f64(1.0).unwrap(),
            mom_groups: 31,
            lambda_mad: Fixed::ZERO,
            lambda_shift: Fixed::ZERO,
            lambda_linear: Fixed::ZERO,
            min_utility: Fixed::from_f64(-100.0).unwrap(),
            max_linear_error: Fixed::from_f64(100.0).unwrap(),
            max_shift: Fixed::from_f64(100.0).unwrap(),
        }
    }

    fn zero_model() -> Model {
        Model {
            w1: vec![vec![Fixed::ZERO; FEATURES]; HIDDEN],
            b1: vec![Fixed::ZERO; HIDDEN],
            w2: vec![Fixed::ZERO; HIDDEN],
            b2: Fixed::ZERO,
        }
    }

    #[test]
    fn evaluate_with_zero_data() {
        let model = zero_model();
        let mut row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        let seller = vec![row.clone(); 100];
        let validation = vec![row.clone(); 100];
        let policy = dummy_policy();
        let seed = [0u8; 32];
        let result = evaluate(&model, &seller, &validation, &policy, &seed).unwrap();
        // Zero model, zero data -> utilities should be near zero.
        assert!(result.u_mom.0 >= -65536 && result.u_mom.0 <= 65536);
        // Should pass because min_utility is very negative.
        assert!(result.pass);
    }

    #[test]
    fn median_of_sorted() {
        let values = vec![
            Fixed::from_f64(1.0).unwrap(),
            Fixed::from_f64(3.0).unwrap(),
            Fixed::from_f64(2.0).unwrap(),
        ];
        let m = median(values).unwrap();
        assert_eq!(m.to_f64(), 2.0);
    }

    #[test]
    fn median_of_single() {
        let values = vec![Fixed::from_f64(42.0).unwrap()];
        let m = median(values).unwrap();
        assert_eq!(m.to_f64(), 42.0);
    }

    #[test]
    fn deterministic_group_seed_sensitive() {
        let seed1 = [0u8; 32];
        let mut seed2 = [0u8; 32];
        seed2[0] = 1;
        let g1 = deterministic_group(0, &seed1, 31);
        let g2 = deterministic_group(0, &seed2, 31);
        assert!(g1 != g2, "different seeds should (usually) produce different groups");
    }

    #[test]
    fn diagonal_shift_zero_for_identical() {
        let mut row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        row.features[0] = Fixed::from_f64(1.0).unwrap();
        let seller = vec![row.clone(); 10];
        let validation = vec![row.clone(); 10];
        let s = diagonal_shift(&seller, &validation).unwrap();
        assert_eq!(s.0, 0);
    }
}
