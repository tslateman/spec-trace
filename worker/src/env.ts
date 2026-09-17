declare global {
  namespace Cloudflare {
    interface Env {
      SPECTRACE_API_KEY: string;
      DASHBOARD_URL: string;
    }
  }
}

export type Env = Cloudflare.Env;
