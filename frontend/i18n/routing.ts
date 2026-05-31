import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["zh-CN", "en", "zh-TW"],
  defaultLocale: "zh-CN",
  localePrefix: "as-needed",
});
