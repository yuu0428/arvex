type CTAProps = {
  title: string;
  description?: string;
  label: string;
  href: string;
};

/**
 * 単独の CTA ブロック。ページの末尾など、1つの行動を強く押し出す用。
 */
export function CTA({ title, description, label, href }: CTAProps) {
  return (
    <section
      className="py-20 sm:py-28 px-6 text-center"
      style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
    >
      <div className="max-w-2xl mx-auto">
        <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-6">{title}</h2>
        {description && <p className="text-lg leading-relaxed opacity-80 mb-10">{description}</p>}
        <a
          href={href}
          className="inline-block px-10 py-5 rounded-full font-medium transition hover:opacity-90"
          style={{ background: "var(--color-neutral)", color: "var(--color-primary)" }}
        >
          {label}
        </a>
      </div>
    </section>
  );
}
