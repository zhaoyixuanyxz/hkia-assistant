"use client";

import { useTranslations } from "next-intl";

import { AmbientBackground } from "@/components/ambient-background";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link, useRouter } from "@/i18n/navigation";
import { setToken } from "@/lib/auth";
import { useState } from "react";

import { PUBLIC_API_PREFIX } from "@/lib/api-base";

const API_BASE = PUBLIC_API_PREFIX;

export default function RegisterPage() {
  const router = useRouter();
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const reg = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName,
        }),
      });
      if (!reg.ok) {
        setError(t("registerFail"));
        return;
      }
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        setError(t("registerLoginFail"));
        return;
      }
      const data = (await res.json()) as { access_token: string };
      setToken(data.access_token);
      router.replace("/conversations");
    } catch {
      setError(t("networkError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-full flex-col overflow-y-auto bg-transparent">
      <AmbientBackground />
      <div className="relative flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-md border-border/70 bg-card/95 shadow-xl shadow-primary/[0.06] backdrop-blur-md ring-1 ring-border/40">
          <CardHeader>
            <CardTitle className="font-serif text-xl tracking-tight">{t("registerTitle")}</CardTitle>
            <CardDescription>{t("registerDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="dn">{t("displayName")}</Label>
                <Input
                  id="dn"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">{t("email")}</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">{t("password")}</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              {error ? (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              ) : null}
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? t("submitPending") : t("registeringSubmit")}
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                {t("haveAccount")}{" "}
                <Link href="/login" className="text-primary underline">
                  {t("toLogin")}
                </Link>
              </p>
              <p className="text-center text-xs">
                <Link href="/guide" className="text-primary underline">
                  {t("footerGuide")}
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
