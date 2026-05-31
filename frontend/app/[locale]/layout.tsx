import type { Metadata } from "next";
import { Geist_Mono, Noto_Sans_SC, Source_Serif_4 } from "next/font/google";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { DisclaimerBanner } from "@/components/disclaimer-banner";
import { routing } from "@/i18n/routing";
import "../globals.css";

const notoSansSC = Noto_Sans_SC({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

const LOCALE_METADATA: Record<
  string,
  { title: string; description: string }
> = {
  "zh-CN": {
    title: "中国人寿海外保险配置助手",
    description: "国寿海外专属场景 · 顾问式对话与配置说明",
  },
  "zh-TW": {
    title: "中國人壽海外保險配置助手",
    description: "國壽海外專屬場景 · 顧問式對話與配置說明",
  },
  en: {
    title: "China Life Overseas — Planning assistant",
    description: "Guided conversations within CLP Overseas public materials",
  },
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const meta = LOCALE_METADATA[locale] ?? LOCALE_METADATA["zh-CN"];
  return {
    title: meta.title,
    description: meta.description,
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      className={`${notoSansSC.variable} ${sourceSerif.variable} ${geistMono.variable} scroll-smooth antialiased`}
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <body className="flex h-dvh max-h-dvh flex-col overflow-hidden bg-transparent text-foreground">
        <NextIntlClientProvider messages={messages}>
          <DisclaimerBanner />
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
