"use client";

import { useLocale, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ReportCharts } from "@/components/report-charts";
import { ReportSupplementDrawer } from "@/components/report-supplement-drawer";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ApiError, apiFetch, apiFetchWithTimeout } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { ConversationSurveyResponse, ReportResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Link, useRouter } from "@/i18n/navigation";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const locale = useLocale();
  const tr = useTranslations("report");
  const id = Number(params.id);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [surveyOpen, setSurveyOpen] = useState(false);
  const [surveyComplete, setSurveyComplete] = useState(false);

  const refreshSurveyStatus = useCallback(async () => {
    if (!getToken()) return;
    try {
      const s = await apiFetch<ConversationSurveyResponse>(`/conversations/${id}/survey`);
      setSurveyComplete(s.required_complete);
    } catch {
      setSurveyComplete(false);
    }
  }, [id]);

  useEffect(() => {
    void refreshSurveyStatus();
  }, [refreshSurveyStatus]);

  async function generate() {
    if (!getToken()) {
      router.replace("/login");
      return;
    }

    if (!surveyComplete) {
      setError(tr("survey.errGenerate"));
      setSurveyOpen(true);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const rep = await apiFetchWithTimeout<ReportResponse>(
        `/conversations/${id}/reports/generate`,
        { method: "POST", body: JSON.stringify({ locale }) },
        120_000
      );
      setReport(rep);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else if (e instanceof ApiError && e.status === 422)
        setError(tr("survey.errGenerate"));
      else if (e instanceof DOMException && e.name === "AbortError")
        setError(tr("timeout"));
      else setError(tr("fail"));
    } finally {
      setLoading(false);
    }
  }

  async function loadLatest() {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setError(null);
    try {
      const rep = await apiFetch<ReportResponse>(
        `/conversations/${id}/reports/latest`
      );
      setReport(rep);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setReport(null);
        return;
      }
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(tr("readFail"));
    }
  }

  useEffect(() => {
    void loadLatest();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- id only
  }, [id]);

  const body = report?.body;

  return (
    <div className="mx-auto max-w-4xl space-y-8 rounded-2xl bg-card/35 px-0 py-4 ring-1 ring-border/35 print:max-w-none print:bg-white print:shadow-none print:ring-0 sm:py-6">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="space-y-1">
          <h1 className="font-serif text-2xl font-semibold tracking-tight sm:text-[1.65rem]">
            {tr("title")}
          </h1>
          <p className="text-xs text-muted-foreground">{tr("subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={!surveyComplete ? "border-amber-600/50 text-amber-900 dark:text-amber-100" : undefined}
            onClick={() => setSurveyOpen(true)}
          >
            {tr("survey.openButton")}
          </Button>
          <Link
            href={`/conversations/${id}/chat`}
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            {tr("backChat")}
          </Link>
          <Button type="button" size="sm" onClick={generate} disabled={loading}>
            {loading ? tr("generating") : report ? tr("regenerate") : tr("generate")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => window.print()}
          >
            {tr("print")}
          </Button>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <ReportSupplementDrawer
        conversationId={id}
        open={surveyOpen}
        onOpenChange={(o) => {
          setSurveyOpen(o);
          if (!o) void refreshSurveyStatus();
        }}
        onSurveyUpdated={({ required_complete }) => {
          setSurveyComplete(required_complete);
        }}
      />
      {!body ? (
        <Card className="print:hidden">
          <CardHeader>
            <CardTitle>{tr("noneTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {tr("noneHint")}
          </CardContent>
        </Card>
      ) : (
        <article className="space-y-6 print:text-foreground">
          <header className="print:break-inside-avoid">
            <h2 className="text-2xl font-semibold tracking-tight">{body.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground print:text-stone-600">
              {body.limited_data_notice}
            </p>
          </header>
          <section className="space-y-2 print:break-inside-avoid">
            <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
              {tr("userBg")}
            </h3>
            <p className="text-sm leading-relaxed">{body.user_background}</p>
          </section>
          <section className="space-y-2 print:break-inside-avoid">
            <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
              {tr("insights")}
            </h3>
            <p className="text-sm leading-relaxed">{body.insights}</p>
          </section>
          <section className="space-y-2 print:break-inside-avoid">
            <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
              {tr("direction")}
            </h3>
            <p className="text-sm leading-relaxed">{body.allocation_direction}</p>
          </section>
          <section className="space-y-2 print:break-inside-avoid">
            <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
              {tr("categories")}
            </h3>
            <p className="text-sm leading-relaxed">{body.product_category_suggestions}</p>
            <p className="text-xs text-amber-700">{tr("categoryNote")}</p>
          </section>
          {body.concrete_product_picks?.length ? (
            <section className="space-y-2 print:break-inside-avoid">
              <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
                {tr("picksTitle")}
              </h3>
              <ul className="space-y-3 text-sm">
                {body.concrete_product_picks.map((p) => (
                  <li
                    key={p.product_id}
                    className="rounded-md border border-border/70 bg-muted/20 p-3"
                  >
                    <div className="font-medium text-foreground">
                      {p.name || tr("refLabel")}
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {tr("refLabel")}: {p.product_id}
                    </p>
                    {p.rationale ? (
                      <p className="mt-2 text-xs leading-relaxed">{p.rationale}</p>
                    ) : null}
                    {p.source_url ? (
                      <a
                        href={p.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-2 inline-block text-xs text-primary underline"
                      >
                        {tr("dataSource")}
                      </a>
                    ) : null}
                    {p.product_id ? (
                      <div className="mt-2">
                        <Link
                          href={`/knowledge/${encodeURIComponent(p.product_id)}`}
                          className="text-xs text-primary underline"
                        >
                          {tr("viewInLibrary")}
                        </Link>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <section className="space-y-2">
            <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
              {tr("risk")}
            </h3>
            <p className="text-sm leading-relaxed">{body.risk_notes}</p>
          </section>
          {body.follow_up_questions?.length ? (
            <section className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground print:text-stone-800">
                {tr("followUp")}
              </h3>
              <ul className="list-inside list-disc text-sm">
                {body.follow_up_questions.map((qitem) => (
                  <li key={qitem}>{qitem}</li>
                ))}
              </ul>
            </section>
          ) : null}
          <Separator className="print:border-stone-200" />
          <section className="print:break-inside-avoid">
            <h3 className="mb-3 text-sm font-medium text-muted-foreground print:text-stone-800">
              {tr("chartsCaption")}
            </h3>
            <ReportCharts charts={body.charts} />
          </section>
          <Separator className="print:border-stone-200" />
          <footer className="rounded-md border border-dashed border-border bg-muted/30 p-4 text-xs leading-relaxed text-muted-foreground print:border-stone-300 print:bg-stone-50 print:text-stone-700">
            <div className="font-medium text-foreground print:text-stone-900">
              {tr("disclaimerTitle")}
            </div>
            <p className="mt-2">{report!.disclaimer_text}</p>
          </footer>
        </article>
      )}
    </div>
  );
}
