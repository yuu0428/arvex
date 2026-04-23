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
 */
export function Card({ title, description, image, imageAlt = "", href, eyebrow }: CardProps) {
  const inner = (
    <div
      className="flex flex-col overflow-hidden rounded-2xl transition hover:-translate-y-0.5"
      style={{
        background: "color-mix(in srgb, var(--color-primary) 4%, transparent)",
      }}
    >
      {image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={image} alt={imageAlt} className="w-full aspect-video object-cover" />
      )}
      <div className="p-6">
        {eyebrow && (
          <p className="text-xs uppercase tracking-widest mb-2 opacity-70">{eyebrow}</p>
        )}
        <h3 className="text-lg font-bold mb-2 leading-snug">{title}</h3>
        {description && <p className="text-sm opacity-80 leading-relaxed">{description}</p>}
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
