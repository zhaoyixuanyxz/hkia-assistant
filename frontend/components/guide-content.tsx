"use client";

import { useTranslations } from "next-intl";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function GuideContent() {
  const t = useTranslations("guide");
  const steps = [t("step1"), t("step2"), t("step3"), t("step4"), t("step5")];

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-0 py-1">
      <div>
        <h1 className="font-serif text-2xl font-semibold tracking-tight text-primary sm:text-[1.65rem]">
          {t("title")}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("intro")}</p>
      </div>
      <ol className="list-decimal space-y-6 pl-5 text-sm leading-relaxed marker:text-primary">
        {steps.map((s, i) => (
          <li key={i} className="pl-2">
            {s}
          </li>
        ))}
      </ol>
      <Card className="border-dashed border-amber-200/70 bg-card/85">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-amber-900">{t("notice")}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          {t("referenceFooter")}
        </CardContent>
      </Card>
    </div>
  );
}
