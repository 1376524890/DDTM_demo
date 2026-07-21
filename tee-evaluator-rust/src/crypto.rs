use anyhow::{bail, Result};
use chacha20poly1305::{aead::{Aead, KeyInit, Payload}, Key, XChaCha20Poly1305, XNonce};
use hkdf::Hkdf;
use rand::{rngs::OsRng, TryRngCore};
use sha2::Sha256;
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::{Zeroize, Zeroizing};

pub struct SessionKey(pub Zeroizing<[u8;32]>);

pub fn new_ephemeral() -> Result<(StaticSecret, PublicKey)> {
    let mut bytes = [0_u8;32];
    OsRng.try_fill_bytes(&mut bytes)?;
    let secret = StaticSecret::from(bytes);
    bytes.zeroize();
    let public = PublicKey::from(&secret);
    Ok((secret, public))
}

pub fn derive(secret: &StaticSecret, peer: &PublicKey, session_id: &[u8]) -> Result<SessionKey> {
    let shared = secret.diffie_hellman(peer);
    let hk = Hkdf::<Sha256>::new(Some(b"DDTM_X25519_V1"), shared.as_bytes());
    let mut key = [0_u8;32];
    hk.expand(session_id, &mut key).map_err(|_| anyhow::anyhow!("HKDF expand"))?;
    Ok(SessionKey(Zeroizing::new(key)))
}

pub fn encrypt(key: &SessionKey, aad: &[u8], plaintext: &[u8]) -> Result<(Vec<u8>, [u8;24])> {
    let cipher = XChaCha20Poly1305::new(Key::from_slice(key.0.as_ref()));
    let mut nonce = [0_u8;24]; OsRng.try_fill_bytes(&mut nonce)?;
    let ciphertext = cipher.encrypt(XNonce::from_slice(&nonce), Payload { msg: plaintext, aad })?;
    Ok((ciphertext, nonce))
}

pub fn decrypt(key: &SessionKey, aad: &[u8], nonce: &[u8;24], ciphertext: &[u8]) -> Result<Vec<u8>> {
    let cipher = XChaCha20Poly1305::new(Key::from_slice(key.0.as_ref()));
    cipher.decrypt(XNonce::from_slice(nonce), Payload { msg: ciphertext, aad }).map_err(|_| anyhow::anyhow!("AEAD authentication failed"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encrypt_decrypt_round_trip() {
        let key = SessionKey(Zeroizing::new([0x42u8; 32]));
        let aad = b"test-aad-data";
        let plaintext = b"Hello, DDTM-QAS! This is a test message.";

        let (ciphertext, nonce) = encrypt(&key, aad, plaintext).unwrap();
        assert_ne!(ciphertext, plaintext, "encryption should change plaintext");

        let decrypted = decrypt(&key, aad, &nonce, &ciphertext).unwrap();
        assert_eq!(decrypted, plaintext, "decrypt should recover plaintext");
    }

    #[test]
    fn aad_authentication_fails() {
        let key = SessionKey(Zeroizing::new([0x42u8; 32]));
        let (ciphertext, nonce) = encrypt(&key, b"correct-aad", b"secret").unwrap();

        // Wrong AAD should fail.
        assert!(decrypt(&key, b"wrong-aad", &nonce, &ciphertext).is_err());
    }

    #[test]
    fn wrong_key_fails() {
        let k1 = SessionKey(Zeroizing::new([0x01u8; 32]));
        let k2 = SessionKey(Zeroizing::new([0x02u8; 32]));
        let (ciphertext, nonce) = encrypt(&k1, b"aad", b"secret").unwrap();

        assert!(decrypt(&k2, b"aad", &nonce, &ciphertext).is_err());
    }

    #[test]
    fn wrong_nonce_fails() {
        let key = SessionKey(Zeroizing::new([0x42u8; 32]));
        let (ciphertext, _) = encrypt(&key, b"aad", b"secret").unwrap();
        let wrong_nonce = [0xFFu8; 24];

        assert!(decrypt(&key, b"aad", &wrong_nonce, &ciphertext).is_err());
    }

    #[test]
    fn key_derivation_same_secrets_yields_same_key() {
        let (s1, p1) = new_ephemeral().unwrap();
        let (s2, p2) = new_ephemeral().unwrap();

        let session_id = b"session-42";
        let k1 = derive(&s1, &p2, session_id).unwrap();
        let k2 = derive(&s2, &p1, session_id).unwrap();

        // Both sides should derive the same key.
        assert_eq!(k1.0.as_ref(), k2.0.as_ref());
    }

    #[test]
    fn key_derivation_different_session_differs() {
        let (s1, p2) = new_ephemeral().unwrap();
        let (_s2, p1) = new_ephemeral().unwrap();

        let k1 = derive(&s1, &p1, b"session-1").unwrap();
        let k2 = derive(&s1, &p1, b"session-2").unwrap();

        assert_ne!(k1.0.as_ref(), k2.0.as_ref());
    }
}
