type HeroProps = {
  eyebrow?: string;
  title: string;
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
  if (variant === "split") {
    return (
      <section className="grid lg:grid-cols-2 min-h-[70vh] gap-0">
        <div className="flex flex-col justify-center p-10 lg:p-16">
          {eyebrow && (
            <p className="text-xs uppercase tracking-widest mb-6 opacity-70">{eyebrow}</p>
          )}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight mb-6">{title}</h1>
          {subtitle && (
            <p className="text-lg leading-relaxed opacity-80 max-w-lg">{subtitle}</p>
          )}
          {ctaLabel && ctaHref && (
            <a
              href={ctaHref}
              className="inline-block mt-10 w-fit px-8 py-4 rounded-full font-medium transition hover:opacity-90"
              style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
            >
              {ctaLabel}
            </a>
          )}
        </div>
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt={imageAlt} className="w-full h-full object-cover min-h-[50vh]" />
        )}
      </section>
    );
  }

  if (variant === "minimal") {
    return (
      <section className="px-6 sm:px-10 lg:px-16 py-24 sm:py-32">
        <div className="max-w-4xl">
          {eyebrow && (
            <p className="text-xs uppercase tracking-widest mb-6 opacity-70">{eyebrow}</p>
          )}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold leading-tight">{title}</h1>
          {subtitle && (
            <p className="text-lg sm:text-xl leading-relaxed mt-8 opacity-80 max-w-2xl">
              {subtitle}
            </p>
          )}
          {ctaLabel && ctaHref && (
            <a
              href={ctaHref}
              className="inline-block mt-10 px-8 py-4 rounded-full font-medium transition hover:opacity-90"
              style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
            >
              {ctaLabel}
            </a>
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
        {eyebrow && (
          <p className="text-xs uppercase tracking-widest mb-6 opacity-70">{eyebrow}</p>
        )}
        <h1 className="text-5xl sm:text-7xl font-bold leading-tight">{title}</h1>
        {subtitle && (
          <p className="mt-8 text-lg sm:text-xl leading-relaxed opacity-80 max-w-2xl mx-auto">
            {subtitle}
          </p>
        )}
        {ctaLabel && ctaHref && (
          <a
            href={ctaHref}
            className="inline-block mt-10 px-8 py-4 rounded-full font-medium transition hover:opacity-90"
            style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
          >
            {ctaLabel}
          </a>
        )}
      </div>
    </section>
  );
}
