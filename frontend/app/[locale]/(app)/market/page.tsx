"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { DataUpdateJob, MarketRow } from "@/lib/types";
import { PUBLIC_API_PREFIX } from "@/lib/api-base";

const API_BASE = PUBLIC_API_PREFIX;

export default function MarketPage() {
  const t = useTranslations("market");
  const [rows, setRows] = useState<MarketRow[]>([]);
  const [updates, setUpdates] = useState<DataUpdateJob[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getToken()) return;
    setError(null);
    try {
      const data = await apiFetch<MarketRow[]>("/market/indicators");
      setRows(data);
      const jobs = await apiFetch<DataUpdateJob[]>("/market/updates");
      setUpdates(jobs);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setError(t("relogin"));
      else setError(t("loadError"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function refresh() {
    const tok = getToken();
    setMsg(null);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/market/refresh`, {
        method: "POST",
        headers: tok ? { Authorization: `Bearer ${tok}` } : {},
      });
      if (!res.ok) throw new Error();
      const data = (await res.json()) as { message?: string };
      setMsg(data.message ?? t("simulatedRefresh"));
      await load();
    } catch {
      setError(t("refreshFail"));
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-0 py-1">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-foreground sm:text-[1.65rem]">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button type="button" size="sm" variant="secondary" onClick={refresh}>
          {t("refresh")}
        </Button>
      </div>
      {msg ? (
        <p className="text-sm text-muted-foreground" role="status">
          {msg}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {rows.map((m) => (
          <Card key={m.id} className="border-border/80 bg-card/80 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{m.name}</CardTitle>
              <CardDescription>{m.value}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>{m.explanation}</p>
              <a
                href={m.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-primary underline"
              >
                {t("sourceLink")}
              </a>
              <div className="text-xs">
                {t("updatedLabel")}: {m.updated_at}
              </div>
              {m.trend_note ? (
                <div className="text-xs text-muted-foreground">
                  {t("trendPrefix")}：{m.trend_note}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
      {updates.length ? (
        <Card className="border-border/80 bg-card/80 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-base">{t("historyTitle")}</CardTitle>
            <CardDescription>{t("historyDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {updates.map((u) => (
              <div key={u.id} className="rounded border border-border/70 p-2">
                <div>
                  {t("jobLabel")} #{u.id}
                </div>
                <div>
                  {t("statusLabel")}：{u.status}
                </div>
                <div>
                  {t("startLabel")}：{u.started_at}
                </div>
                <div>
                  {t("endLabel")}：{u.finished_at ?? "-"}
                </div>
                {u.error_message ? (
                  <div>
                    {t("errorLabel")}：{u.error_message}
                  </div>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
