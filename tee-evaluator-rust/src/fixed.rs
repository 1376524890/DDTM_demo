use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};

pub const FRAC_BITS: u32 = 16;
pub const ONE: i64 = 1_i64 << FRAC_BITS;

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Fixed(pub i64);

impl Fixed {
    pub const ZERO: Fixed = Fixed(0);
    pub const ONE: Fixed = Fixed(ONE);

    pub fn from_f64(v: f64) -> Result<Self> {
        if !v.is_finite() { bail!("non-finite fixed-point input") }
        let scaled = (v * ONE as f64).round_ties_even();
        if scaled < i64::MIN as f64 || scaled > i64::MAX as f64 { bail!("fixed-point overflow") }
        Ok(Fixed(scaled as i64))
    }

    pub fn to_f64(self) -> f64 { self.0 as f64 / ONE as f64 }

    pub fn checked_add(self, rhs: Self) -> Result<Self> {
        Ok(Fixed(self.0.checked_add(rhs.0).ok_or_else(|| anyhow::anyhow!("add overflow"))?))
    }

    pub fn checked_sub(self, rhs: Self) -> Result<Self> {
        Ok(Fixed(self.0.checked_sub(rhs.0).ok_or_else(|| anyhow::anyhow!("sub overflow"))?))
    }

    pub fn checked_mul(self, rhs: Self) -> Result<Self> {
        let product = self.0 as i128 * rhs.0 as i128;
        let shifted = product >> FRAC_BITS;
        if shifted < i64::MIN as i128 || shifted > i64::MAX as i128 { bail!("mul overflow") }
        Ok(Fixed(shifted as i64))
    }

    pub fn checked_div_int(self, divisor: i64) -> Result<Self> {
        if divisor == 0 { bail!("division by zero") }
        Ok(Fixed(self.0 / divisor))
    }

    pub fn abs(self) -> Self { Fixed(self.0.saturating_abs()) }
    pub fn max(self, rhs: Self) -> Self { if self.0 >= rhs.0 { self } else { rhs } }
    pub fn min(self, rhs: Self) -> Self { if self.0 <= rhs.0 { self } else { rhs } }
    pub fn clamp(self, low: Self, high: Self) -> Self { self.max(low).min(high) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_from_f64_basic() {
        let a = Fixed::from_f64(1.0).unwrap();
        assert_eq!(a.0, 65536);
        let b = Fixed::from_f64(0.5).unwrap();
        assert_eq!(b.0, 32768);
        let c = Fixed::from_f64(-1.0).unwrap();
        assert_eq!(c.0, -65536);
    }

    #[test]
    fn fixed_add_sub() {
        let a = Fixed::from_f64(1.5).unwrap();
        let b = Fixed::from_f64(2.5).unwrap();
        let sum = a.checked_add(b).unwrap();
        assert!((sum.to_f64() - 4.0).abs() < 0.001);
        let diff = b.checked_sub(a).unwrap();
        assert!((diff.to_f64() - 1.0).abs() < 0.001);
    }

    #[test]
    fn fixed_mul() {
        let a = Fixed::from_f64(2.0).unwrap();
        let b = Fixed::from_f64(3.0).unwrap();
        let product = a.checked_mul(b).unwrap();
        assert!((product.to_f64() - 6.0).abs() < 0.1);
    }

    #[test]
    fn fixed_overflow_rejected() {
        let a = Fixed(i64::MAX);
        let b = Fixed(1);
        assert!(a.checked_add(b).is_err());
    }

    #[test]
    fn fixed_clamp() {
        let low = Fixed::from_f64(-1.0).unwrap();
        let high = Fixed::from_f64(1.0).unwrap();
        let v = Fixed::from_f64(5.0).unwrap();
        assert!((v.clamp(low, high).to_f64() - 1.0).abs() < 0.01);
    }
}
