"use client";

import {
  BookOpen,
  Library,
  LogOut,
  MessageSquare,
  TrendingUp,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AmbientBackground } from "@/components/ambient-background";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { apiFetch } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

const navIcons = {
  "/conversations": MessageSquare,
  "/knowledge": Library,
  "/market": TrendingUp,
  "/reference": BookOpen,
} as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("nav");
  const ts = useTranslations("shell");
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");

  const nav = [
    { href: "/conversations", label: t("conversations") },
    { href: "/knowledge", label: t("knowledge") },
    { href: "/market", label: t("market") },
    { href: "/reference", label: t("guide") },
  ] as const;

  function logout() {
    clearToken();
    router.push("/login");
  }

  useEffect(() => {
    const tk = getToken();
    if (!tk) {
      router.replace("/login");
      return;
    }
    apiFetch<{ email: string }>("/auth/me")
      .then((u) => {
        setEmail(u.email);
        setReady(true);
      })
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
  }, [router]);

  if (!ready) {
    return (
      <div className="relative flex min-h-0 flex-1 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <AmbientBackground />
        <div
          className="size-8 animate-pulse rounded-full border-2 border-primary/30 border-t-primary"
          aria-hidden
        />
        <span>{ts("loading")}</span>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-0 flex-1 w-full bg-transparent">
      <AmbientBackground />
      <aside className="sticky top-0 flex max-h-full min-h-0 w-[min(17.5rem,100%)] shrink-0 flex-col self-stretch overflow-y-auto border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-[4px_0_24px_-12px_rgba(15,23,42,0.35)] print:hidden">
        <div className="space-y-1 px-5 pb-5 pt-6">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-sidebar-primary">
            {ts("brandBadge")}
          </p>
          <h1 className="font-serif text-lg font-semibold leading-snug tracking-tight text-sidebar-foreground">
            {ts("productName")}
          </h1>
          <p className="text-xs leading-relaxed text-sidebar-foreground/65">
            {ts("brandSub")}
          </p>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3 pb-4" aria-label={ts("navAria")}>
          {nav.map((item) => {
            const active =
              item.href === "/conversations"
                ? pathname.startsWith("/conversations")
                : pathname.startsWith(item.href);
            const Icon = navIcons[item.href];
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/45 hover:text-sidebar-foreground",
                )}
              >
                <Icon
                  className={cn(
                    "size-4 shrink-0 transition-opacity",
                    active ? "opacity-100" : "opacity-70 group-hover:opacity-100",
                  )}
                  aria-hidden
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-sidebar-border/80 bg-sidebar/95 px-3 py-3 [&_.text-muted-foreground]:text-sidebar-foreground/55 [&_button]:border-transparent [&_button]:text-sidebar-foreground [&_button:hover]:bg-sidebar-accent/45">
          <LocaleSwitcher />
          <Separator className="my-3 bg-sidebar-border/70" />
          <div className="flex flex-col gap-3">
            <div
              className="truncate rounded-lg bg-sidebar-accent/35 px-3 py-2 text-xs text-sidebar-foreground/85"
              title={email}
            >
              {email}
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="w-full gap-2 border-sidebar-border/60 bg-sidebar-accent/40 text-sidebar-foreground hover:bg-sidebar-accent/55"
              onClick={logout}
            >
              <LogOut className="size-3.5 opacity-90" aria-hidden />
              {ts("logout")}
            </Button>
          </div>
        </div>
      </aside>

      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-background/95 shadow-[inset_1px_0_0_oklch(0_0_0/0.06)]">
        <header
          role="banner"
          className="sticky top-0 z-20 flex h-[3.25rem] shrink-0 items-center justify-between gap-4 border-b border-border/70 bg-card/85 px-5 backdrop-blur-md print:hidden"
        >
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              {ts("tagline")}
            </span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="hidden shrink-0 gap-2 sm:inline-flex"
            onClick={logout}
          >
            <LogOut className="size-3.5 opacity-80" aria-hidden />
            {ts("logout")}
          </Button>
        </header>

        <main className="relative min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-y-contain bg-[linear-gradient(180deg,oklch(0.995_0.004_95)_0%,var(--background)_18%,var(--background)_100%)] [scrollbar-gutter:stable]">
          <div className="mx-auto min-h-full w-full max-w-[min(72rem,calc(100%-2rem))] px-4 pb-10 pt-6 sm:px-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
