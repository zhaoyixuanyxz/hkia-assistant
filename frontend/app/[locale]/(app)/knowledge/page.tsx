"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { ProductStub } from "@/lib/types";
import { Link } from "@/i18n/navigation";

export default function KnowledgePage() {
  const t = useTranslations("knowledge");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<string>("");
  const [mode, setMode] = useState<"keyword" | "semantic">("keyword");
  const [rows, setRows] = useState<ProductStub[]>([]);
  const [error, setError] = useState<string | null>(null);

  const categories = useMemo(() => ["", "医疗", "人寿", "储蓄", "重疾"], []);

  const load = useCallback(async () => {
    if (!getToken()) return;
    setError(null);
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (category) params.set("category", category);
      params.set("mode", mode);
      const path = `/knowledge/products?${params.toString()}`;
      const data = await apiFetch<ProductStub[]>(path);
      setRows(data);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setError(t("relogin"));
      else setError(t("loadError"));
    }
  }, [q, category, mode, t]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-0 py-1">
      <div>
        <h1 className="font-serif text-2xl font-semibold tracking-tight text-foreground sm:text-[1.65rem]">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Input
          className="max-w-xs"
          placeholder={t("searchPlaceholder")}
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <Button
              key={c || "all"}
              type="button"
              size="sm"
              variant={category === c ? "secondary" : "outline"}
              onClick={() => setCategory(c)}
            >
              {!c ? t("allCategories") : c}
            </Button>
          ))}
        </div>
        <Button type="button" size="sm" onClick={() => setQ(qInput)}>
          {t("searchBtn")}
        </Button>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "keyword" ? "secondary" : "outline"}
            onClick={() => setMode("keyword")}
          >
            {t("modeKeyword")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "semantic" ? "secondary" : "outline"}
            onClick={() => setMode("semantic")}
          >
            {t("modeSemantic")}
          </Button>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {rows.map((p) => (
          <Card
            key={p.id}
            className="border-border/80 bg-card/80 backdrop-blur-sm transition-colors hover:bg-muted/25"
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                <Link
                  href={`/knowledge/${encodeURIComponent(p.id)}`}
                  className="text-foreground underline-offset-4 hover:underline"
                >
                  {p.name}
                </Link>
              </CardTitle>
              <CardDescription>
                {p.category} ·{" "}
                <span className="text-amber-600">
                  {p.is_sample ? t("sampleData") : t("realData")}
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>{p.summary}</p>
              <Link
                href={`/knowledge/${encodeURIComponent(p.id)}`}
                className="text-xs text-primary underline"
              >
                {t("sourceLink")}
              </Link>
              <div className="text-xs">
                {t("updatedLabel")}: {p.updated_at}
              </div>
              {p.match_reason ? (
                <div className="text-xs">
                  {t("matchLabel")}: {p.match_reason}
                  {typeof p.match_score === "number"
                    ? `（${p.match_score.toFixed(3)}）`
                    : ""}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
