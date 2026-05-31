"use client";

import { useLocale } from "next-intl";
import { useTransition } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";

const LOCALES = routing.locales;

export function LocaleSwitcher() {
  const t = useTranslations("locale");
  const pathname = usePathname();
  const router = useRouter();
  const locale = useLocale();
  const [pending, start] = useTransition();

  return (
    <div className="flex flex-wrap gap-1 p-2 text-[11px]">
      <span className="w-full shrink-0 text-muted-foreground">{t("label")}</span>
      {LOCALES.map((loc) => (
        <Button
          key={loc}
          type="button"
          size="sm"
          variant="ghost"
          disabled={pending}
          className={cn(
            "h-7 px-2",
            loc === locale && "bg-sidebar-accent font-medium"
          )}
          onClick={() => {
            start(() => router.replace(pathname, { locale: loc }));
          }}
        >
          {t(loc)}
        </Button>
      ))}
    </div>
  );
}
