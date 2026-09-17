export type Account = {
  readonly id: string;
  readonly password: string;
  locked: boolean;
};

export type Session = {
  readonly token: string;
  readonly subject: string;
  readonly expiresAt: number;
};

export const SESSION_TTL_MS = 60 * 60 * 1000;

export class SessionStore {
  private readonly accounts = new Map<string, Account>();
  private readonly sessions = new Map<string, Session>();
  private issued = 0;

  register(account: Account): void {
    this.accounts.set(account.id, account);
  }

  setLocked(id: string, locked: boolean): void {
    const account = this.accounts.get(id);
    if (!account) throw new Error(`no account ${id}`);
    account.locked = locked;
  }

  signIn(id: string, password: string, now: number): Session | null {
    const account = this.accounts.get(id);
    if (!account || account.locked || account.password !== password) return null;
    const session: Session = {
      token: `tok-${(this.issued += 1)}`,
      subject: id,
      expiresAt: now + SESSION_TTL_MS,
    };
    this.sessions.set(session.token, session);
    return session;
  }

  resolve(token: string, now: number): string | null {
    const session = this.sessions.get(token);
    if (!session || session.expiresAt <= now) return null;
    return session.subject;
  }
}
