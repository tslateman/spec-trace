import { beforeEach, describe, expect, it } from "vitest";
import { SESSION_TTL_MS, SessionStore } from "../src/session";

const NOW = 1_700_000_000_000;

let store: SessionStore;

beforeEach(() => {
  store = new SessionStore();
  store.register({ id: "ada", password: "correct horse", locked: false });
});

// A tag on the describe block links every test inside it.
describe("POST /sessions [SES-AUTH-001]", () => {
  it("issues a token naming its subject", () => {
    const session = store.signIn("ada", "correct horse", NOW);

    expect(session?.subject).toBe("ada");
  });

  it("issues no token for a wrong password", () => {
    expect(store.signIn("ada", "battery staple", NOW)).toBeNull();
  });

  it("[SES-AUTH-002] issues no token for a locked account", () => {
    store.setLocked("ada", true);

    expect(store.signIn("ada", "correct horse", NOW)).toBeNull();
  });
});

describe("[SES-AUTH-002] unlocking an account", () => {
  it("restores sign-in", () => {
    store.setLocked("ada", true);
    store.setLocked("ada", false);

    expect(store.signIn("ada", "correct horse", NOW)).not.toBeNull();
  });
});

describe("GET /sessions/current [SES-TTL-001]", () => {
  it("resolves a token inside its hour", () => {
    const session = store.signIn("ada", "correct horse", NOW);

    expect(store.resolve(session!.token, NOW + SESSION_TTL_MS - 1)).toBe("ada");
  });

  it("resolves nothing past the hour", () => {
    const session = store.signIn("ada", "correct horse", NOW);

    expect(store.resolve(session!.token, NOW + SESSION_TTL_MS)).toBeNull();
  });
});
