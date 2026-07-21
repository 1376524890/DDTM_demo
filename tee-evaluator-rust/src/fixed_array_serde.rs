//! Serde support for large fixed-size arrays ([T; 128]) used in DDTM-QAS.
//! serde's derive macro only supports arrays up to 32 elements.
//! This module provides serializer/deserializer for [T; 128].

use serde::de::{self, Deserializer, SeqAccess, Visitor};
use serde::ser::{SerializeTuple, Serializer};
use std::fmt;

pub mod fixed128 {
    use super::*;
    use crate::fixed::Fixed;

    pub fn serialize<S>(arr: &[Fixed; 128], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut seq = serializer.serialize_tuple(128)?;
        for elem in arr.iter() {
            seq.serialize_element(&elem.0)?;
        }
        seq.end()
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<[Fixed; 128], D::Error>
    where
        D: Deserializer<'de>,
    {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = [Fixed; 128];
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("128 signed integers (Q16.16)")
            }
            fn visit_seq<A>(self, mut seq: A) -> Result<[Fixed; 128], A::Error>
            where
                A: SeqAccess<'de>,
            {
                let mut arr = [Fixed::ZERO; 128];
                for (i, e) in arr.iter_mut().enumerate() {
                    *e = Fixed(seq.next_element::<i64>()?.ok_or_else(|| {
                        de::Error::invalid_length(i, &self)
                    })?);
                }
                Ok(arr)
            }
        }
        deserializer.deserialize_tuple(128, V)
    }
}
