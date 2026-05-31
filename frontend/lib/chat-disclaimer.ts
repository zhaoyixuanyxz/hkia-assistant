/** Mirrors `backend/app/compliance.py` — keep in sync for message splitting. */
export const CHAT_STANDARD_DISCLAIMER =
  "本内容由 AI 根据用户提供的信息和公开资料生成，仅供一般信息参考，不构成持牌财务、保险、税务、法律或投资建议。" +
  "保险产品条款、费用、收益、保障范围和适用性应以保险公司正式文件及持牌专业人士意见为准。" +
  "请在作出任何购买或配置决定前，咨询合资格专业顾问。";

const CHAT_SHORT_DISCLAIMER =
  "以上内容仅供参考，不构成持牌建议。正式条款及适合性请以保险公司文件与合资格顾问意见为准。";

/** Common model / legacy inline endings (longest first for matching). */
const DISCLAIMER_SUFFIXES: string[] = [
  CHAT_STANDARD_DISCLAIMER,
  "「以上内容仅供一般信息参考，不构成持牌财务、保险、税务或法律建议；具体条款以保险公司正式文件及合资格专业人士意见为准。」",
  "以上内容仅供一般信息参考，不构成持牌财务、保险、税务或法律建议；具体条款以保险公司正式文件及合资格专业人士意见为准。",
  CHAT_SHORT_DISCLAIMER,
];

function trimBody(raw: string): string {
  return raw.replace(/\s+$/u, "").trim();
}

/**
 * Splits stored assistant text into user-facing body vs compliance footer for UI styling.
 */
export function splitAssistantMessage(content: string): {
  body: string;
  disclaimer: string | null;
} {
  const t = content.trim();
  if (!t) return { body: "", disclaimer: null };

  for (const suffix of DISCLAIMER_SUFFIXES) {
    if (t === suffix) {
      return { body: "", disclaimer: suffix };
    }
    if (t.endsWith(suffix)) {
      const before = t.slice(0, t.length - suffix.length);
      return { body: trimBody(before), disclaimer: suffix };
    }
    const sep = `\n\n${suffix}`;
    if (t.endsWith(sep)) {
      return {
        body: trimBody(t.slice(0, t.length - sep.length)),
        disclaimer: suffix,
      };
    }
  }

  return { body: t, disclaimer: null };
}
