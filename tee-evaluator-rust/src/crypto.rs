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
