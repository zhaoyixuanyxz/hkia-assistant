"use client";

import { useTranslations } from "next-intl";

import { AmbientBackground } from "@/components/ambient-background";
import { GuideContent } from "@/components/guide-content";
import { buttonVariants } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

export default function PublicGuidePage() {
  const th = useTranslations("home");
  const ts = useTranslations("shell");

  return (
    <div className="relative min-h-full overflow-y-auto bg-transparent">
      <AmbientBackground />
      <div className="relative mx-auto max-w-3xl space-y-6 px-4 py-10">
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card/85 px-5 py-4 shadow-sm backdrop-blur-md">
          <div className="font-serif text-base font-semibold tracking-tight text-primary">
            {ts("productName")}
          </div>
          <div className="flex gap-2">
            <Link
              href="/login"
              className={cn(buttonVariants({ size: "sm", variant: "default" }))}
            >
              {th("gotoLogin")}
            </Link>
            <Link
              href="/register"
              className={cn(buttonVariants({ size: "sm", variant: "outline" }))}
            >
              {th("gotoRegister")}
            </Link>
          </div>
        </header>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {th("publicBanner")}
        </p>
        <GuideContent />
      </div>
    </div>
  );
}
