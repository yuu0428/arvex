type CardProps = {
  title: string;
  description?: string;
  image?: string;
  imageAlt?: string;
  href?: string;
  eyebrow?: string;
};

/**
 * 汎用カード。image + eyebrow + title + description + 任意リンク。
 *
 * ベースライン interaction:
 * - mobile: active 時に 0.98 に縮む（押した感）
 * - desktop: hover で 1.02 に拡大、内側画像が 1.06 にズーム、影が深化
 */
export function Card({ title, description, image, imageAlt = "", href, eyebrow }: CardProps) {
  const inner = (
    <div
      className={[
        "group flex flex-col overflow-hidden rounded-2xl relative",
        "transition-[transform,box-shadow] duration-300 ease-out will-change-transform",
        "hover:shadow-[0_20px_60px_-20px_rgba(0,0,0,0.18)]",
        "motion-safe:hover:-translate-y-1 motion-safe:active:scale-[0.98]",
      ].join(" ")}
      style={{
        background: "color-mix(in srgb, var(--color-primary) 4%, transparent)",
        border: "1px solid color-mix(in srgb, var(--color-primary) 8%, transparent)",
      }}
    >
      {image && (
        <div className="overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={image}
            alt={imageAlt}
            className="w-full aspect-video object-cover transition-transform duration-[600ms] ease-out group-hover:scale-[1.06]"
          />
        </div>
      )}
      <div className="p-6">
        {eyebrow && (
          <p
            className="text-xs uppercase tracking-widest mb-2 opacity-70"
            style={{ color: "color-mix(in srgb, var(--color-primary) 70%, transparent)" }}
          >
            {eyebrow}
          </p>
        )}
        <h3 className="text-lg font-bold mb-2 leading-snug">{title}</h3>
        {description && (
          <p className="text-sm opacity-80 leading-relaxed">{description}</p>
        )}
        {href && (
          <span
            aria-hidden
            className="mt-4 inline-block text-sm opacity-60 transition-[transform,opacity] group-hover:translate-x-1 group-hover:opacity-100"
          >
            →
          </span>
        )}
      </div>
    </div>
  );
  return href ? (
    <a href={href} className="block no-underline" style={{ color: "inherit" }}>
      {inner}
    </a>
  ) : (
    inner
  );
}
