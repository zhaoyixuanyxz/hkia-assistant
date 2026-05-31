"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type {
  ConversationSurveyResponse,
  ReportSurveyTemplate,
  SurveyTemplateField,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const OPTIONAL_IDS: string[] = [
  "existing_coverage_summary",
  "mortgage_debts_band",
  "liquid_assets_band",
  "smoking",
  "health_notes",
  "education_funding_note",
  "target_retirement_age",
  "mpf_note",
  "currency_preference",
  "existing_policies_free_text",
];

const GOAL_VALUES = [
  "death_disability",
  "medical_hospital",
  "critical_illness",
  "wealth_savings",
  "retirement_income",
  "education_legacy",
] as const;

function blank(v: unknown): boolean {
  if (v == null) return true;
  if (typeof v === "string") return v.trim() === "";
  if (Array.isArray(v)) return v.length === 0;
  return false;
}

function optionalFilledCount(answers: Record<string, unknown>): number {
  let n = 0;
  for (const k of OPTIONAL_IDS) {
    if (!blank(answers[k])) n += 1;
  }
  return n;
}

function requiredComplete(answers: Record<string, unknown>): boolean {
  const req = [
    "age_band",
    "residency_region",
    "marital_dependents_summary",
    "occupation_category",
    "income_band",
    "premium_afford_ratio_band",
  ];
  for (const k of req) {
    if (blank(answers[k])) return false;
  }
  const g = answers.primary_goals;
  if (!Array.isArray(g) || g.length === 0) return false;
  for (const x of g) {
    if (!GOAL_VALUES.includes(x as (typeof GOAL_VALUES)[number])) return false;
  }
  return true;
}

function depthPreview(answers: Record<string, unknown>): string | null {
  if (!requiredComplete(answers)) return null;
  const o = optionalFilledCount(answers);
  if (o >= 8) return "deep";
  if (o >= 4) return "enhanced";
  return "standard";
}

type Props = {
  conversationId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSurveyUpdated: (s: {
    required_complete: boolean;
    report_depth: string | null;
  }) => void;
};

function coerceAnswers(raw: Record<string, unknown> | undefined): Record<string, unknown> {
  const a: Record<string, unknown> = {};
  const keys = [
    "age_band",
    "residency_region",
    "marital_dependents_summary",
    "occupation_category",
    "income_band",
    "premium_afford_ratio_band",
    "primary_goals",
    ...OPTIONAL_IDS,
  ];
  for (const k of keys) {
    a[k] = raw?.[k];
  }
  const goalsRaw = raw?.primary_goals;
  const goals: string[] = [];
  if (Array.isArray(goalsRaw)) {
    for (const x of goalsRaw) {
      const s = String(x).trim();
      if (s && !goals.includes(s)) goals.push(s);
    }
  }
  a.primary_goals = goals;
  for (const k of keys) {
    if (k === "primary_goals") continue;
    const v = a[k];
    a[k] = typeof v === "string" ? v : v == null ? "" : String(v);
  }
  for (const k of OPTIONAL_IDS) {
    const v = a[k];
    a[k] = typeof v === "string" ? v : v == null ? "" : String(v);
  }
  return a;
}

export function ReportSupplementDrawer({
  conversationId,
  open,
  onOpenChange,
  onSurveyUpdated,
}: Props) {
  const t = useTranslations("report");
  const [template, setTemplate] = useState<ReportSurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState<string>("draft");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    if (!getToken()) return;
    setLoading(true);
    setMsg(null);
    try {
      const [tpl, sur] = await Promise.all([
        apiFetch<ReportSurveyTemplate>("/meta/report-survey-template"),
        apiFetch<ConversationSurveyResponse>(`/conversations/${conversationId}/survey`),
      ]);
      setTemplate(tpl);
      setAnswers(coerceAnswers(sur.answers as Record<string, unknown>));
      setStatus(sur.status || "draft");
      onSurveyUpdated({
        required_complete: sur.required_complete,
        report_depth: sur.report_depth,
      });
    } catch {
      setMsg(t("survey.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [conversationId, onSurveyUpdated, t]);

  useEffect(() => {
    if (open) void loadAll();
  }, [open, loadAll]);

  const applySurveyResponse = useCallback(
    (sur: ConversationSurveyResponse) => {
      setAnswers(coerceAnswers(sur.answers as Record<string, unknown>));
      setStatus(sur.status || "draft");
      onSurveyUpdated({
        required_complete: sur.required_complete,
        report_depth: sur.report_depth,
      });
    },
    [onSurveyUpdated]
  );

  const putSurvey = async (body: {
    status: string;
    merge_to_profile: boolean;
    sync_to_user_library: boolean;
  }) => {
    if (!getToken()) return;
    setMsg(null);
    try {
      const sur = await apiFetch<ConversationSurveyResponse>(
        `/conversations/${conversationId}/survey`,
        {
          method: "PUT",
          body: JSON.stringify({
            answers,
            ...body,
          }),
        }
      );
      applySurveyResponse(sur);
      setMsg(t("survey.saved"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setMsg(t("survey.errMerge"));
      } else {
        setMsg(t("survey.saveFailed"));
      }
    }
  };

  const depthKey = depthPreview(answers);
  const reqOk = requiredComplete(answers);

  const renderField = (f: SurveyTemplateField) => {
    const label = t(`survey.fieldLabels.${f.id}` as "survey.fieldLabels.age_band");
    const v = answers[f.id];

    if (f.input === "multiselect" && f.id === "primary_goals") {
      return (
        <div key={f.id} className="space-y-2">
          <Label className="text-xs font-medium text-foreground/90">{label}</Label>
          <div className="grid gap-2 sm:grid-cols-2">
            {GOAL_VALUES.map((gv) => {
              const selected = Array.isArray(v) && v.includes(gv);
              return (
                <label
                  key={gv}
                  className={cn(
                    "flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-xs transition-colors",
                    selected
                      ? "border-primary/50 bg-primary/10"
                      : "border-border/60 bg-muted/20 hover:bg-muted/35"
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={!!selected}
                    onChange={() => {
                      setAnswers((prev) => {
                        const cur = Array.isArray(prev.primary_goals)
                          ? [...(prev.primary_goals as string[])]
                          : [];
                        const i = cur.indexOf(gv);
                        if (i >= 0) cur.splice(i, 1);
                        else cur.push(gv);
                        return { ...prev, primary_goals: cur };
                      });
                    }}
                  />
                  <span className="leading-snug">
                    {t(`survey.goalLabels.${gv}` as "survey.goalLabels.death_disability")}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      );
    }

    if (f.input === "select" && Array.isArray(f.options)) {
      return (
        <div key={f.id} className="space-y-1.5">
          <Label className="text-xs font-medium text-foreground/90">{label}</Label>
          <select
            className={cn(
              "flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm",
              "ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            )}
            value={typeof v === "string" ? v : ""}
            onChange={(e) =>
              setAnswers((prev) => ({ ...prev, [f.id]: e.target.value }))
            }
          >
            <option value="">—</option>
            {f.options.map((opt) => {
              const val = typeof opt === "string" ? opt : opt.value;
              const dis = typeof opt === "string" ? opt : opt.label;
              return (
                <option key={val} value={val}>
                  {dis}
                </option>
              );
            })}
          </select>
        </div>
      );
    }

    if (f.input === "textarea") {
      return (
        <div key={f.id} className="space-y-1.5">
          <Label className="text-xs font-medium text-foreground/90">{label}</Label>
          <Textarea
            value={typeof v === "string" ? v : ""}
            maxLength={f.max_len ?? undefined}
            rows={3}
            className="min-h-[72px] resize-y text-sm"
            onChange={(e) =>
              setAnswers((prev) => ({ ...prev, [f.id]: e.target.value }))
            }
          />
        </div>
      );
    }

    return (
      <div key={f.id} className="space-y-1.5">
        <Label className="text-xs font-medium text-foreground/90">{label}</Label>
        <Input
          value={typeof v === "string" ? v : ""}
          maxLength={f.max_len ?? undefined}
          placeholder={f.placeholder ?? ""}
          className="text-sm"
          onChange={(e) =>
            setAnswers((prev) => ({ ...prev, [f.id]: e.target.value }))
          }
        />
      </div>
    );
  };

  if (!open) return null;

  return (
    <div className="print:hidden">
      <button
        type="button"
        aria-label="Close overlay"
        className="fixed inset-0 z-50 bg-stone-950/45 backdrop-blur-[2px] transition-opacity animate-in fade-in-0"
        onClick={() => onOpenChange(false)}
      />
      <aside
        className={cn(
          "fixed right-0 top-0 z-[60] flex h-full w-[min(100vw,26.5rem)] flex-col",
          "border-l border-amber-900/15 bg-gradient-to-b from-card via-card to-amber-50/30 shadow-2xl",
          "dark:from-card dark:via-card dark:to-stone-950/80 dark:border-border",
          "animate-in slide-in-from-right duration-200"
        )}
      >
        <header className="shrink-0 space-y-1 border-b border-border/60 px-4 pb-3 pt-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h2 className="font-serif text-lg font-semibold tracking-tight text-foreground">
                {t("survey.title")}
              </h2>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{t("survey.subtitle")}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="shrink-0 -mr-1 h-8 text-xs"
              onClick={() => onOpenChange(false)}
            >
              {t("survey.close")}
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="rounded-full bg-stone-900 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-100 dark:bg-stone-100 dark:text-stone-900">
              {t("survey.depthLabel")}
            </span>
            <span className="text-xs text-muted-foreground">
              {!reqOk
                ? "—"
                : depthKey === "deep"
                  ? t("survey.depthDeep")
                  : depthKey === "enhanced"
                    ? t("survey.depthEnhanced")
                    : t("survey.depthStandard")}
            </span>
            {loading ? (
              <span className="text-[10px] text-muted-foreground">…</span>
            ) : null}
          </div>
          {msg ? (
            <p className="text-[11px] text-amber-800 dark:text-amber-200">{msg}</p>
          ) : null}
        </header>

        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-6 px-4 py-4 pr-5">
            {template ? (
              <>
                <section className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-transparent" />
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                      {t("survey.requiredSection")}
                    </span>
                    <span className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-transparent" />
                  </div>
                  <div className="space-y-4">{template.required.map(renderField)}</div>
                </section>
                <Separator />
                <section className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-transparent" />
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                      {t("survey.optionalSection")}
                    </span>
                    <span className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-transparent" />
                  </div>
                  <div className="space-y-4">{template.optional.map(renderField)}</div>
                </section>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">…</p>
            )}
          </div>
        </ScrollArea>

        <footer className="shrink-0 space-y-2 border-t border-border/60 bg-card/90 px-4 py-3 backdrop-blur-sm">
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="text-xs"
              disabled={loading}
              onClick={() =>
                putSurvey({
                  status: "draft",
                  merge_to_profile: false,
                  sync_to_user_library: false,
                })
              }
            >
              {t("survey.saveDraft")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="default"
              className="text-xs"
              disabled={loading || !reqOk}
              onClick={() =>
                putSurvey({ status: "saved", merge_to_profile: true, sync_to_user_library: false })
              }
            >
              {t("survey.saveMerge")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="text-xs"
              disabled={loading}
              onClick={() =>
                putSurvey({
                  status,
                  merge_to_profile: false,
                  sync_to_user_library: true,
                })
              }
            >
              {t("survey.saveLibrary")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="text-xs"
              disabled={loading}
              onClick={async () => {
                if (!confirm(t("survey.loadConfirm"))) return;
                try {
                  const sur = await apiFetch<ConversationSurveyResponse>(
                    `/conversations/${conversationId}/survey/pull-from-library`,
                    { method: "POST" }
                  );
                  applySurveyResponse(sur);
                  setMsg(t("survey.saved"));
                } catch {
                  setMsg(t("survey.loadFailed"));
                }
              }}
            >
              {t("survey.loadLibrary")}
            </Button>
          </div>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="w-full text-xs text-destructive hover:text-destructive"
            disabled={loading}
            onClick={async () => {
              if (!confirm(t("survey.clearConfirm"))) return;
              try {
                await apiFetch(`/conversations/${conversationId}/survey`, {
                  method: "DELETE",
                });
                setAnswers(coerceAnswers({}));
                setStatus("draft");
                onSurveyUpdated({ required_complete: false, report_depth: null });
                setMsg(t("survey.saved"));
              } catch {
                setMsg(t("survey.saveFailed"));
              }
            }}
          >
            {t("survey.clearLocal")}
          </Button>
        </footer>
      </aside>
    </div>
  );
}
