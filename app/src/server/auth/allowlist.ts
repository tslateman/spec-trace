export function allowedLogins(raw: string | undefined): string[] {
  if (!raw) throw new Error("ALLOWED_LOGINS is not configured");
  return raw
    .split(",")
    .map((login) => login.trim().toLowerCase())
    .filter(Boolean);
}

export function isAllowed(raw: string | undefined, login: string): boolean {
  return allowedLogins(raw).includes(login.toLowerCase());
}
