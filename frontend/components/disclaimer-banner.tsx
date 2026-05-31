"use client";

import { useTranslations } from "next-intl";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function DisclaimerBanner() {
  const t = useTranslations("DisclaimerBanner");
  const [open, setOpen] = useState(false);
  return (
    <div
      className={cn(
        "shrink-0 border-b border-primary/15 bg-gradient-to-r from-primary/[0.07] via-background to-background print:hidden",
      )}
    >
      <div className="mx-auto flex max-w-[min(72rem,calc(100%-2rem))] items-center gap-3 px-4 py-2.5 sm:px-6">
        <span
          className="hidden h-9 w-1 shrink-0 rounded-full bg-primary/55 sm:block"
          aria-hidden
        />
        <span className="min-w-0 flex-1 text-xs leading-snug text-foreground/90 sm:text-[13px]">
          {t("summary")}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 shrink-0 gap-1.5 px-2 text-xs text-primary hover:bg-primary/10 hover:text-primary"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <>
              {t("collapse")} <ChevronUp className="size-3.5 opacity-80" />
            </>
          ) : (
            <>
              {t("expand")} <ChevronDown className="size-3.5 opacity-80" />
            </>
          )}
        </Button>
      </div>
      {open ? (
        <div className="border-t border-border/60 bg-muted/25">
          <p className="mx-auto max-w-[min(72rem,calc(100%-2rem))] px-4 py-3 text-[11px] leading-relaxed text-muted-foreground sm:px-6 sm:text-xs">
            {t("full")}
          </p>
        </div>
      ) : null}
    </div>
  );
}
