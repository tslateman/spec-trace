//! Rust names a `#[test]` function with an identifier, and an identifier holds
//! no brackets. `libtest-mimic` names each trial at run time instead, so the
//! requirement tag reaches the JUnit report exactly as written here.

use libtest_mimic::{Arguments, Failed, Trial};
use storage_vault::{Key, Vault};

const HOUR: u64 = 3_600;

fn seal_hides_the_plaintext() -> Result<(), Failed> {
    let key = Key::new("key-2026-09", 0x5a);
    let mut vault = Vault::new();
    vault.store("invoice.pdf", b"total due", &key, HOUR);

    assert_ne!(vault.sealed("invoice.pdf").unwrap().bytes(), b"total due");
    Ok(())
}

fn open_returns_the_plaintext() -> Result<(), Failed> {
    let key = Key::new("key-2026-09", 0x5a);
    let mut vault = Vault::new();
    vault.store("invoice.pdf", b"total due", &key, HOUR);

    assert_eq!(vault.open("invoice.pdf", &key)?, b"total due");
    Ok(())
}

fn open_refuses_the_wrong_key() -> Result<(), Failed> {
    let key = Key::new("key-2026-09", 0x5a);
    let other = Key::new("key-2026-08", 0x17);
    let mut vault = Vault::new();
    vault.store("invoice.pdf", b"total due", &key, HOUR);

    assert!(vault.open("invoice.pdf", &other).is_err());
    Ok(())
}

fn sealed_document_names_its_key() -> Result<(), Failed> {
    let key = Key::new("key-2026-09", 0x5a);
    let mut vault = Vault::new();
    vault.store("invoice.pdf", b"total due", &key, HOUR);

    assert_eq!(vault.sealed("invoice.pdf").unwrap().key_id, "key-2026-09");
    Ok(())
}

fn rotation_separates_the_key_ids() -> Result<(), Failed> {
    let old = Key::new("key-2026-08", 0x17);
    let new = Key::new("key-2026-09", 0x5a);
    let mut vault = Vault::new();
    vault.store("old.pdf", b"total due", &old, HOUR);
    vault.store("new.pdf", b"total due", &new, HOUR);

    assert_ne!(
        vault.sealed("old.pdf").unwrap().key_id,
        vault.sealed("new.pdf").unwrap().key_id
    );
    Ok(())
}

fn sweep_keeps_a_document_inside_its_window() -> Result<(), Failed> {
    let key = Key::new("key-2026-09", 0x5a);
    let mut vault = Vault::new();
    vault.store("invoice.pdf", b"total due", &key, 2 * HOUR);
    vault.sweep(HOUR);

    assert_eq!(vault.open("invoice.pdf", &key)?, b"total due");
    Ok(())
}

fn sweep_removes_only_the_expired_documents() -> Result<(), Failed> {
    let key = Key::new("key-2026-09", 0x5a);
    let mut vault = Vault::new();
    vault.store("expired.pdf", b"total due", &key, HOUR);
    vault.store("current.pdf", b"total due", &key, 3 * HOUR);
    vault.sweep(2 * HOUR);

    assert_eq!(vault.len(), 1);
    assert!(vault.sealed("expired.pdf").is_none());
    Ok(())
}

fn main() {
    let trials = vec![
        Trial::test(
            "[VLT-ENC-001] seals a document before it lands",
            seal_hides_the_plaintext,
        ),
        Trial::test(
            "[VLT-ENC-001] opens a sealed document",
            open_returns_the_plaintext,
        ),
        Trial::test(
            "[VLT-ENC-001] refuses the wrong key",
            open_refuses_the_wrong_key,
        ),
        Trial::test(
            "[VLT-ENC-002] names the key that sealed it",
            sealed_document_names_its_key,
        ),
        Trial::test(
            "[VLT-ENC-002] separates the key ids a rotation writes",
            rotation_separates_the_key_ids,
        ),
        Trial::test(
            "[VLT-RET-001] keeps a document inside its window",
            sweep_keeps_a_document_inside_its_window,
        ),
        Trial::test(
            "[VLT-RET-001] sweeps only the expired documents",
            sweep_removes_only_the_expired_documents,
        ),
    ];
    libtest_mimic::run(&Arguments::from_args(), trials).exit();
}
