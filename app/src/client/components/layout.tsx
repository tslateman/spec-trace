import { ChevronDown, Moon, PanelLeftClose, PanelLeftOpen, Sun } from "lucide-react";
import type * as React from "react";
import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { Button } from "@/client/components/ui/button";
import { getJson } from "@/client/lib/api";
import { cn } from "@/client/lib/utils";
import { type NavGroup, navigation } from "@/client/navigation";

type Theme = "light" | "dark" | null;

function storedTheme(): Theme {
  try {
    const value = localStorage.getItem("theme");
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function useTheme() {
  const [theme, setTheme] = useState<Theme>(storedTheme);

  useEffect(() => {
    if (theme) {
      document.documentElement.dataset.theme = theme;
      try {
        localStorage.setItem("theme", theme);
      } catch {
        return;
      }
    } else {
      delete document.documentElement.dataset.theme;
    }
  }, [theme]);

  function toggle() {
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const current = theme ?? (systemDark ? "dark" : "light");
    setTheme(current === "dark" ? "light" : "dark");
  }

  const effectiveDark =
    theme === "dark" ||
    (theme === null && typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  return { toggle, effectiveDark };
}

function storedCollapsed(): boolean {
  try {
    return localStorage.getItem("sidebar") === "collapsed";
  } catch {
    return false;
  }
}

function useCollapsed() {
  const [collapsed, setCollapsed] = useState(storedCollapsed);

  useEffect(() => {
    try {
      localStorage.setItem("sidebar", collapsed ? "collapsed" : "expanded");
    } catch {
      return;
    }
  }, [collapsed]);

  return { collapsed, toggle: () => setCollapsed((value) => !value) };
}

function useLogin() {
  const [login, setLogin] = useState<string | null>(null);

  useEffect(() => {
    getJson<{ login: string }>("/api/me", "session")
      .then((session) => setLogin(session.login))
      .catch(() => setLogin(null));
  }, []);

  return login;
}

function useHiddenBelow() {
  const ref = useRef<HTMLElement>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const measure = () => setHidden(node.scrollHeight - node.scrollTop - node.clientHeight > 1);
    measure();
    node.addEventListener("scroll", measure);
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    for (const child of node.children) observer.observe(child);
    return () => {
      node.removeEventListener("scroll", measure);
      observer.disconnect();
    };
  }, []);

  return { ref, hidden };
}

function NavSection({ group, collapsed, divided }: { group: NavGroup; collapsed: boolean; divided: boolean }) {
  return (
    <div className={cn("flex flex-col py-1.5", divided && "border-t border-border")}>
      {!collapsed && (
        <div className="px-3 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {group.title}
        </div>
      )}
      {group.items.map((item) => (
        <NavLink
          key={item.href}
          to={item.href}
          end={item.href === "/"}
          title={collapsed ? item.label : undefined}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded-md py-1.5 text-sm font-medium",
              collapsed ? "justify-center px-0" : "px-3",
              isActive
                ? "bg-sidebar-active text-sidebar-active-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )
          }
        >
          <item.icon className="size-4 shrink-0" aria-hidden="true" />
          {!collapsed && <span className="truncate">{item.label}</span>}
        </NavLink>
      ))}
    </div>
  );
}

export function Shell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  const { toggle, effectiveDark } = useTheme();
  const sidebar = useCollapsed();
  const login = useLogin();
  const collapsed = sidebar.collapsed;
  const docsGroup = navigation.find((group) => group.title === "Docs");
  const primaryGroups = navigation.filter((group) => group !== docsGroup);
  const primaryNav = useHiddenBelow();

  return (
    <div className="flex min-h-screen">
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-sidebar md:flex",
          collapsed ? "w-14" : "w-64",
        )}
      >
        <div className={cn("flex h-14 items-center gap-1 border-b border-border", collapsed ? "px-2" : "px-3")}>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 shrink-0 px-0 text-muted-foreground hover:text-foreground"
            onClick={sidebar.toggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
          >
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </Button>
          {!collapsed && (
            <NavLink to="/" className="truncate px-1 text-sm font-bold tracking-tight">
              SpecTrace Dashboard
            </NavLink>
          )}
        </div>
        <div className="relative flex min-h-0 flex-1 flex-col">
          <nav
            ref={primaryNav.ref}
            aria-label="Primary"
            className="flex min-h-0 flex-1 flex-col overflow-auto px-2 py-1"
          >
            {primaryGroups.map((group, index) => (
              <NavSection key={group.title} group={group} collapsed={collapsed} divided={index > 0} />
            ))}
          </nav>
          {primaryNav.hidden && (
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-0 bottom-0 flex h-7 items-end justify-center bg-gradient-to-t from-sidebar via-sidebar/80 to-transparent"
            >
              <ChevronDown className="size-3.5 text-muted-foreground" />
            </div>
          )}
        </div>
        {docsGroup && (
          <nav aria-label="Documentation" className="shrink-0 border-t border-border px-2 py-1">
            <NavSection group={docsGroup} collapsed={collapsed} divided={false} />
          </nav>
        )}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-3 border-b border-border px-6">
          {login && <span className="text-sm text-muted-foreground">{login}</span>}
          <Button variant="ghost" size="sm" onClick={toggle} aria-label="Toggle theme">
            {effectiveDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          <a href="/auth/logout" className="text-sm font-medium text-muted-foreground hover:text-foreground">
            Sign out
          </a>
        </header>
        <main className="flex-1 p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
