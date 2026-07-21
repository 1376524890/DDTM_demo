use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use crate::{data::{Row, FEATURES}, fixed::Fixed};

pub const HIDDEN: usize = 64;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Model {
    pub w1: Vec<Vec<Fixed>>, // [64][128]
    pub b1: Vec<Fixed>,      // [64]
    pub w2: Vec<Fixed>,      // [64]
    pub b2: Fixed,
}

#[derive(Clone, Debug)]
pub struct Forward {
    pub pre: [Fixed; HIDDEN],
    pub hidden: [Fixed; HIDDEN],
    pub score: Fixed,
}

#[derive(Clone, Debug)]
pub struct Gradient {
    pub w1: Vec<Vec<i128>>,
    pub b1: Vec<i128>,
    pub w2: Vec<i128>,
    pub b2: i128,
    pub samples: usize,
}

impl Gradient {
    pub fn zero() -> Self {
        Self { w1: vec![vec![0; FEATURES]; HIDDEN], b1: vec![0; HIDDEN], w2: vec![0; HIDDEN], b2: 0, samples: 0 }
    }
}

impl Model {
    pub fn validate(&self) -> Result<()> {
        if self.w1.len() != HIDDEN || self.b1.len() != HIDDEN || self.w2.len() != HIDDEN { bail!("model shape mismatch") }
        if self.w1.iter().any(|r| r.len() != FEATURES) { bail!("w1 shape mismatch") }
        Ok(())
    }

    pub fn forward(&self, row: &Row) -> Result<Forward> {
        let mut pre = [Fixed::ZERO; HIDDEN];
        let mut hidden = [Fixed::ZERO; HIDDEN];
        for j in 0..HIDDEN {
            let mut sum = self.b1[j];
            for k in 0..FEATURES { sum = sum.checked_add(self.w1[j][k].checked_mul(row.features[k])?)?; }
            pre[j] = sum;
            hidden[j] = if sum.0 > 0 { sum } else { Fixed::ZERO };
        }
        let mut score = self.b2;
        for j in 0..HIDDEN { score = score.checked_add(self.w2[j].checked_mul(hidden[j])?)?; }
        Ok(Forward { pre, hidden, score })
    }

    pub fn hinge_loss(&self, row: &Row) -> Result<Fixed> {
        let score = self.forward(row)?.score;
        let signed = if row.label == 1 { score } else { Fixed(-score.0) };
        Ok(Fixed::ONE.checked_sub(signed)?.max(Fixed::ZERO))
    }

    pub fn accumulate_gradient(&self, row: &Row, out: &mut Gradient) -> Result<()> {
        if !row.valid { return Ok(()) }
        let f = self.forward(row)?;
        let signed_score = if row.label == 1 { f.score } else { Fixed(-f.score.0) };
        if signed_score.0 >= Fixed::ONE.0 { out.samples += 1; return Ok(()) }
        let dy: i128 = -(row.label as i128); // derivative in integer coefficient; scale applied by activations.
        for j in 0..HIDDEN {
            out.w2[j] += dy * f.hidden[j].0 as i128;
            if f.pre[j].0 > 0 {
                let dh = (dy * self.w2[j].0 as i128) >> 16;
                out.b1[j] += dh;
                for k in 0..FEATURES {
                    out.w1[j][k] += (dh * row.features[k].0 as i128) >> 16;
                }
            }
        }
        out.b2 += dy << 16;
        out.samples += 1;
        Ok(())
    }

    pub fn one_step(&self, grad: &Gradient, learning_rate: Fixed, clip: Fixed) -> Result<Model> {
        if grad.samples == 0 { bail!("empty gradient") }
        let n = grad.samples as i128;
        let update = |value: Fixed, total: i128| -> Result<Fixed> {
            let avg = total / n;
            let clipped = avg.clamp(-(clip.0 as i128), clip.0 as i128);
            let delta = (learning_rate.0 as i128 * clipped) >> 16;
            let next = value.0 as i128 - delta;
            if next < i64::MIN as i128 || next > i64::MAX as i128 { bail!("parameter update overflow") }
            Ok(Fixed(next as i64))
        };
        let mut next = self.clone();
        for j in 0..HIDDEN {
            next.b1[j] = update(self.b1[j], grad.b1[j])?;
            next.w2[j] = update(self.w2[j], grad.w2[j])?;
            for k in 0..FEATURES { next.w1[j][k] = update(self.w1[j][k], grad.w1[j][k])?; }
        }
        next.b2 = update(self.b2, grad.b2)?;
        Ok(next)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::Row;
    use crate::fixed::Fixed;

    fn dummy_model() -> Model {
        Model {
            w1: vec![vec![Fixed::ZERO; FEATURES]; HIDDEN],
            b1: vec![Fixed::ZERO; HIDDEN],
            w2: vec![Fixed::ZERO; HIDDEN],
            b2: Fixed::ZERO,
        }
    }

    #[test]
    fn model_validate_passes() {
        let m = dummy_model();
        assert!(m.validate().is_ok());
    }

    #[test]
    fn model_validate_bad_shape_fails() {
        let m = Model {
            w1: vec![vec![Fixed::ZERO; FEATURES]; 32],
            b1: vec![Fixed::ZERO; HIDDEN],
            w2: vec![Fixed::ZERO; HIDDEN],
            b2: Fixed::ZERO,
        };
        assert!(m.validate().is_err());
    }

    #[test]
    fn forward_zero_model() {
        let m = dummy_model();
        let row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        let f = m.forward(&row).unwrap();
        assert_eq!(f.score.0, 0);
    }

    #[test]
    fn gradient_zero_on_saturated_hinge() {
        let mut m = dummy_model();
        // Set b2 large positive so margin > 1 for label=1.
        m.b2 = Fixed::from_f64(10.0).unwrap();
        let row = Row {
            row_id: 0,
            valid: true,
            label: 1,
            timestamp: 1700000000,
            missing_mask: [0u8; 16],
            features: [Fixed::ZERO; FEATURES],
        };
        let mut g = Gradient::zero();
        m.accumulate_gradient(&row, &mut g).unwrap();
        assert_eq!(g.samples, 1);
        // All gradient components should be zero (hinge saturated).
        for j in 0..HIDDEN {
            assert_eq!(g.w2[j], 0);
            assert_eq!(g.b1[j], 0);
        }
        assert_eq!(g.b2, 0);
    }
}
