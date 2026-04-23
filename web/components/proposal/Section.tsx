import { ReactNode } from "react";

type SectionProps = {
  eyebrow?: string;
  title?: string;
  intro?: string;
  tone?: "default" | "muted" | "inverted";
  children: ReactNode;
};

/**
 * 一般的なセクション枠。eyebrow + title + intro を持てる。
 * tone で背景色を切り替え。
 */
export function Section({
  eyebrow,
  title,
  intro,
  tone = "default",
  children,
}: SectionProps) {
  const bgStyle =
    tone === "muted"
      ? { background: "var(--color-secondary)", color: "var(--color-neutral)" }
      : tone === "inverted"
        ? { background: "var(--color-primary)", color: "var(--color-neutral)" }
        : {};
  return (
    <section className="py-20 sm:py-28 px-6 sm:px-10 lg:px-16" style={bgStyle}>
      <div className="max-w-6xl mx-auto">
        {(eyebrow || title || intro) && (
          <div className="mb-12 sm:mb-16 max-w-3xl">
            {eyebrow && (
              <p className="text-xs uppercase tracking-widest mb-4 opacity-70">{eyebrow}</p>
            )}
            {title && (
              <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-6">{title}</h2>
            )}
            {intro && <p className="text-base sm:text-lg leading-relaxed opacity-80">{intro}</p>}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}
