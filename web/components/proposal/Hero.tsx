import { ReactNode } from "react";
import { TextReveal } from "./motion/TextReveal";
import { Reveal } from "./motion/Reveal";

type HeroProps = {
  eyebrow?: string;
  /** 文字列なら内部で TextReveal に包む。React 要素で来たらそのまま描画（Claude が二重 wrap した時の保険）。 */
  title: ReactNode;
  subtitle?: string;
  image?: string;
  imageAlt?: string;
  ctaLabel?: string;
  ctaHref?: string;
  variant?: "centered" | "split" | "minimal";
};

/**
 * ページトップのヒーロー。variant で3種の構図を選べる。
 * - centered: 中央寄せ、背景画像あり
 * - split: 左テキスト / 右画像
 * - minimal: 左寄せテキストのみ
 *
 * h1 は内部で TextReveal されるため、MDX 側で TextReveal を書く必要はない。
 */
export function Hero({
  eyebrow,
  title,
  subtitle,
  image,
  imageAlt = "",
  ctaLabel,
  ctaHref,
  variant = "centered",
}: HeroProps) {
  const eyebrowEl = eyebrow && (
    <Reveal variant="fade" delay={0.0} duration={0.6}>
      <p className="text-xs uppercase tracking-widest mb-6 opacity-70">{eyebrow}</p>
    </Reveal>
  );

  const titleEl =
    typeof title === "string" ? (
      <TextReveal by="word" stagger={0.06}>
        {title}
      </TextReveal>
    ) : (
      title
    );

  const subtitleEl = subtitle && (
    <Reveal variant="up" delay={0.45} duration={1.0} distance={20}>
      <p className="text-lg sm:text-xl leading-relaxed opacity-80 max-w-2xl">
        {subtitle}
      </p>
    </Reveal>
  );

  const ctaEl = ctaLabel && ctaHref && (
    <Reveal variant="up" delay={0.7} duration={0.9} distance={16}>
      <a
        href={ctaHref}
        className="inline-flex items-center gap-2 mt-8 px-8 py-4 rounded-full font-medium transition-[background,color,transform] duration-300 hover:scale-[1.03] active:scale-[0.97]"
        style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
      >
        {ctaLabel}
        <span aria-hidden className="transition-transform duration-300 group-hover:translate-x-1">→</span>
      </a>
    </Reveal>
  );

  if (variant === "split") {
    return (
      <section className="grid lg:grid-cols-2 min-h-[70vh] gap-0">
        <div className="flex flex-col justify-center p-10 lg:p-16">
          {eyebrowEl}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight mb-6">
            {titleEl}
          </h1>
          {subtitleEl}
          {ctaEl}
        </div>
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt={imageAlt}
            className="w-full h-full object-cover min-h-[50vh]"
          />
        )}
      </section>
    );
  }

  if (variant === "minimal") {
    return (
      <section className="px-6 sm:px-10 lg:px-16 py-24 sm:py-32">
        <div className="max-w-4xl">
          {eyebrowEl}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold leading-tight">
            {titleEl}
          </h1>
          {subtitle && (
            <Reveal variant="up" delay={0.45} duration={1.0} distance={20}>
              <p className="text-lg sm:text-xl leading-relaxed mt-8 opacity-80 max-w-2xl">
                {subtitle}
              </p>
            </Reveal>
          )}
          {ctaLabel && ctaHref && (
            <Reveal variant="up" delay={0.7} duration={0.9} distance={16}>
              <a
                href={ctaHref}
                className="inline-flex items-center gap-2 mt-10 px-8 py-4 rounded-full font-medium transition-[background,color,transform] duration-300 hover:scale-[1.03] active:scale-[0.97]"
                style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
              >
                {ctaLabel}
                <span aria-hidden>→</span>
              </a>
            </Reveal>
          )}
        </div>
      </section>
    );
  }

  // centered (default)
  return (
    <section className="relative min-h-[80vh] flex items-center justify-center overflow-hidden">
      {image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={image}
          alt={imageAlt}
          className="absolute inset-0 w-full h-full object-cover opacity-40"
        />
      )}
      <div className="relative text-center px-6 max-w-4xl">
        {eyebrowEl}
        <h1 className="text-5xl sm:text-7xl font-bold leading-tight">{titleEl}</h1>
        {subtitle && (
          <Reveal variant="up" delay={0.45} duration={1.0} distance={20}>
            <p className="mt-8 text-lg sm:text-xl leading-relaxed opacity-80 max-w-2xl mx-auto">
              {subtitle}
            </p>
          </Reveal>
        )}
        {ctaLabel && ctaHref && (
          <Reveal variant="up" delay={0.7} duration={0.9} distance={16}>
            <a
              href={ctaHref}
              className="inline-flex items-center gap-2 mt-10 px-8 py-4 rounded-full font-medium transition-[background,color,transform] duration-300 hover:scale-[1.03] active:scale-[0.97]"
              style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
            >
              {ctaLabel}
              <span aria-hidden>→</span>
            </a>
          </Reveal>
        )}
      </div>
    </section>
  );
}
