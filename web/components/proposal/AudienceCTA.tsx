type AudienceCTAProps = {
  audience: string;
  description?: string;
  label: string;
  href: string;
};

/**
 * 相手別 CTA。複数をグリッドで並べると「誰向け」が明示される構成になる。
 */
export function AudienceCTA({ audience, description, label, href }: AudienceCTAProps) {
  return (
    <div
      className={[
        "group p-8 rounded-2xl flex flex-col transition-[transform,box-shadow,border-color] duration-300",
        "motion-safe:hover:-translate-y-1 hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.18)]",
      ].join(" ")}
      style={{
        background: "color-mix(in srgb, var(--color-primary) 4%, transparent)",
        border: "1px solid color-mix(in srgb, var(--color-primary) 10%, transparent)",
      }}
    >
      <h3 className="text-lg font-bold mb-3">{audience}</h3>
      {description && (
        <p className="text-sm opacity-80 leading-relaxed mb-6 flex-1">{description}</p>
      )}
      <a
        href={href}
        className={[
          "inline-flex items-center gap-2 w-fit px-6 py-3 rounded-full text-sm font-medium",
          "transition-[transform,background,color] duration-300",
          "hover:scale-[1.04] active:scale-[0.96]",
        ].join(" ")}
        style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
      >
        {label}
        <span
          aria-hidden
          className="transition-transform duration-300 group-hover:translate-x-1"
        >
          →
        </span>
      </a>
    </div>
  );
}
