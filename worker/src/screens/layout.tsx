import type { Context } from "hono";
import { html } from "hono/html";
import type { Child } from "hono/jsx";

export function renderScreen(c: Context, screen: Child) {
  return c.html(html`<!DOCTYPE html>${screen}`);
}
