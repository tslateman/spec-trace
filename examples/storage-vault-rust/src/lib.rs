//! A storage vault that seals documents on write and forgets them on expiry.

use std::collections::HashMap;

#[derive(Debug, PartialEq, Eq)]
pub struct SealError;

impl std::fmt::Display for SealError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "the vault refused to open the document")
    }
}

impl std::error::Error for SealError {}

#[derive(Clone, Debug)]
pub struct Sealed {
    pub key_id: String,
    pub expires_at: u64,
    bytes: Vec<u8>,
}

impl Sealed {
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }
}

#[derive(Clone, Debug)]
pub struct Key {
    pub id: String,
    secret: u8,
}

impl Key {
    pub fn new(id: &str, secret: u8) -> Self {
        Key {
            id: id.to_string(),
            secret,
        }
    }
}

#[derive(Default)]
pub struct Vault {
    documents: HashMap<String, Sealed>,
}

impl Vault {
    pub fn new() -> Self {
        Vault::default()
    }

    pub fn store(&mut self, name: &str, plaintext: &[u8], key: &Key, expires_at: u64) {
        let sealed = Sealed {
            key_id: key.id.clone(),
            expires_at,
            bytes: plaintext.iter().map(|byte| byte ^ key.secret).collect(),
        };
        self.documents.insert(name.to_string(), sealed);
    }

    pub fn sealed(&self, name: &str) -> Option<&Sealed> {
        self.documents.get(name)
    }

    pub fn open(&self, name: &str, key: &Key) -> Result<Vec<u8>, SealError> {
        let sealed = self.documents.get(name).ok_or(SealError)?;
        if sealed.key_id != key.id {
            return Err(SealError);
        }
        Ok(sealed.bytes.iter().map(|byte| byte ^ key.secret).collect())
    }

    pub fn sweep(&mut self, now: u64) {
        self.documents.retain(|_, sealed| sealed.expires_at > now);
    }

    pub fn len(&self) -> usize {
        self.documents.len()
    }

    pub fn is_empty(&self) -> bool {
        self.documents.is_empty()
    }
}
