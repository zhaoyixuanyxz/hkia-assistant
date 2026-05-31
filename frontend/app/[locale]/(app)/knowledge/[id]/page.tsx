"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { ProductDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Link, useRouter } from "@/i18n/navigation";

export default function KnowledgeProductDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("knowledge");
  const td = useTranslations("knowledgeDetail");
  const rawId = params.id;
  const id = Array.isArray(rawId) ? rawId[0] : rawId;
  const [row, setRow] = useState<ProductDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getToken() || !id) return;
    setError(null);
    try {
      const enc = encodeURIComponent(id);
      const data = await apiFetch<ProductDetail>(`/knowledge/products/${enc}`);
      setRow(data);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else if (e instanceof ApiError && e.status === 404) setError("notfound");
      else setError("load");
    }
  }, [id, router]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-0 py-1">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/knowledge"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          {td("back")}
        </Link>
        <h1 className="font-serif text-xl font-semibold tracking-tight md:text-2xl">
          {t("title")}
        </h1>
      </div>

      {error === "notfound" ? (
        <Card className="border-destructive/40 bg-card/80">
          <CardHeader>
            <CardTitle className="text-base">{td("notFoundTitle")}</CardTitle>
            <CardDescription>{td("notFoundDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/knowledge"
              className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
            >
              {td("backToList")}
            </Link>
          </CardContent>
        </Card>
      ) : error === "load" ? (
        <p className="text-sm text-destructive" role="alert">
          {td("loadError")}
        </p>
      ) : !row ? (
        <p className="text-sm text-muted-foreground">{td("loading")}</p>
      ) : (
        <Card className="border-border/80 bg-card/80 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xl">{row.name}</CardTitle>
            <CardDescription>
              {row.category} ·{" "}
              <span className="text-amber-600">
                {row.is_sample ? t("sampleData") : t("realData")}
              </span>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            {row.highlights ? (
              <section className="space-y-1">
                <h2 className="text-xs font-medium text-foreground">
                  {td("highlights")}
                </h2>
                <p className="leading-relaxed whitespace-pre-wrap">
                  {row.highlights}
                </p>
              </section>
            ) : null}
            {row.coverage_summary ? (
              <section className="space-y-1">
                <h2 className="text-xs font-medium text-foreground">
                  {td("coverage")}
                </h2>
                <p className="leading-relaxed whitespace-pre-wrap">
                  {row.coverage_summary}
                </p>
              </section>
            ) : null}
            {row.target_audience ? (
              <section className="space-y-1">
                <h2 className="text-xs font-medium text-foreground">
                  {td("audience")}
                </h2>
                <p className="leading-relaxed whitespace-pre-wrap">
                  {row.target_audience}
                </p>
              </section>
            ) : null}
            {row.clause_summary ? (
              <section className="space-y-1">
                <h2 className="text-xs font-medium text-foreground">
                  {td("clauses")}
                </h2>
                <p className="leading-relaxed whitespace-pre-wrap">
                  {row.clause_summary}
                </p>
              </section>
            ) : null}
            {row.source_note ? (
              <section className="space-y-1">
                <h2 className="text-xs font-medium text-foreground">
                  {td("sourceNote")}
                </h2>
                <p className="leading-relaxed whitespace-pre-wrap">
                  {row.source_note}
                </p>
              </section>
            ) : null}
            {row.official_url ? (
              <div className="space-y-1">
                <a
                  href={row.official_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block text-sm text-primary underline"
                >
                  {t("sourceLink")}
                </a>
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  {td("externalHint")}
                </p>
              </div>
            ) : null}
            <div className="text-xs">
              {t("updatedLabel")}: {row.updated_at}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
