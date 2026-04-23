type QuoteProps = {
  children?: string;
  quote?: string;
  author?: string;
  source?: string;
};

/**
 * 引用ブロック。
 */
export function Quote({ children, quote, author, source }: QuoteProps) {
  const text = quote || children;
  return (
    <blockquote
      className="border-l-4 pl-6 py-2 my-8"
      style={{ borderColor: "var(--color-accent)" }}
    >
      <p className="text-xl sm:text-2xl leading-relaxed font-medium">{text}</p>
      {(author || source) && (
        <footer className="mt-4 text-sm opacity-70">
          {author && <span>— {author}</span>}
          {author && source && <span className="mx-2">·</span>}
          {source && <cite className="not-italic">{source}</cite>}
        </footer>
      )}
    </blockquote>
  );
}
