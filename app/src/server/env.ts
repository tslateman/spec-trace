export type Bindings = {
  ASSETS: Fetcher;
  SPECTRACE: Fetcher;
  SPECTRACE_URL: string;
  SPECTRACE_API_KEY: string;
  SESSION_SECRET: string;
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  ALLOWED_LOGINS: string;
  DASHBOARD_API_KEY: string;
  DEV_LOGIN?: string;
};

export type Variables = {
  login: string;
};

export type AppEnv = { Bindings: Bindings; Variables: Variables };
