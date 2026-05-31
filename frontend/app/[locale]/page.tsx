"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useEffect } from "react";

import { getToken } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  const t = useTranslations("home");

  useEffect(() => {
    if (getToken()) router.replace("/conversations");
    else router.replace("/login");
  }, [router]);

  return (
    <div className="relative flex min-h-full items-center justify-center bg-transparent px-4 py-12 text-sm text-muted-foreground">
      {t("redirecting")}
    </div>
  );
}
