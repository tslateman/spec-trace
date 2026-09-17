# Storage Vault (Rust)

A Rust example that links `cargo test` trials to requirements through the
bracketed tag SpecTrace reads from any JUnit report.

The vault seals every document before it lands (`VLT-ENC-001`), names the key
that sealed it (`VLT-ENC-002`), and forgets a document once its retention window
closes (`VLT-RET-001`).

## Layout

```
storage-vault-rust/
├── spectrace-map.yaml           # project: storage-vault
├── specs/vault/
│   ├── VLT-001.md               # Root requirement
│   ├── VLT-ENC-001.md           # Seal on write
│   ├── VLT-ENC-002.md           # Key identifier
│   └── VLT-RET-001.md           # Retention window
├── .config/nextest.toml         # JUnit profile
├── src/lib.rs
├── tests/vault.rs
└── ci/github-actions.yml
```

## Linking a test

Rust names a `#[test]` function with an identifier, and an identifier holds no
brackets. `libtest-mimic` names each trial at run time instead, so the tag
reaches the report exactly as written:

```rust
use libtest_mimic::{Arguments, Trial};

fn main() {
    let trials = vec![Trial::test(
        "[VLT-ENC-001] seals a document before it lands",
        seal_hides_the_plaintext,
    )];
    libtest_mimic::run(&Arguments::from_args(), trials).exit();
}
```

The target that holds those trials declares its own harness:

```toml
[dev-dependencies]
libtest-mimic = "0.8"

[[test]]
name = "vault"
harness = false
```

A plain `#[test] fn vlt_enc_001_seals_on_write()` reaches the report as
`vlt_enc_001_seals_on_write`, which carries no tag and links nothing.

## Running it

`cargo test` writes no JUnit. `cargo nextest` does, on stable, from a profile:

```toml
# .config/nextest.toml
[profile.ci.junit]
path = "junit.xml"
```

```bash
cargo install cargo-nextest --locked
cargo nextest run --profile ci
```

```
    Starting 7 tests across 2 binaries
        PASS [   0.008s] (1/7) storage-vault::vault [VLT-ENC-001] seals a document before it lands
        PASS [   0.008s] (2/7) storage-vault::vault [VLT-ENC-002] names the key that sealed it
        ...
     Summary [   0.009s] 7 tests run: 7 passed, 0 skipped
```

The report lands at `target/nextest/ci/junit.xml`.

## Pushing

One file carries both the links and the results:

```bash
spectrace push --specs specs --links target/nextest/ci/junit.xml --replace
spectrace results push target/nextest/ci/junit.xml
```

`ci/github-actions.yml` runs the same three commands on every change.
