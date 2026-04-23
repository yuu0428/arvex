type Color = string;
type Dimension = string | number;

type TypographyToken = {
  fontFamily?: string;
  fontSize?: Dimension;
  fontWeight?: number | string;
  lineHeight?: Dimension;
  letterSpacing?: Dimension;
};

// MDX runtime compiler (next-mdx-remote/rsc) がネストオブジェクトリテラルを
// 属性値として正しく渡せないため、JSON 文字列も受け入れる。
type MaybeJson<T> = T | string;

type ThemeProps = {
  name?: string;
  /** DESIGN.md colors map (primary, secondary, ...). CSS var --color-<name>。JSON 文字列でも渡せる */
  colors?: MaybeJson<Record<string, Color>>;
  /** DESIGN.md typography map (h1, body-md, label-sm, ...). JSON 文字列でも渡せる */
  typography?: MaybeJson<Record<string, TypographyToken>>;
  /** rounded: xs/sm/md/lg/xl/full → --rounded-<name>。JSON 文字列でも渡せる */
  rounded?: MaybeJson<Record<string, Dimension>>;
  /** spacing: xs/sm/md/lg/xl → --space-<name>。JSON 文字列でも渡せる */
  spacing?: MaybeJson<Record<string, Dimension>>;
  /** ページ全体の base 値 */
  bodyTypography?: string; // typography key を指定（例: "body-md"）
  bodyColor?: string; // colors key
  bgColor?: string; // colors key
};

function parseMaybeJson<T>(v: MaybeJson<T> | undefined, fallback: T): T {
  if (v === undefined || v === null) return fallback;
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v) as T;
  } catch {
    return fallback;
  }
}

function dim(v: Dimension | undefined): string | undefined {
  if (v === undefined) return undefined;
  return typeof v === "number" ? `${v}` : v;
}

/**
 * DESIGN.md のトークン全体をページに注入する。
 *
 * - Google Fonts を一括ロード
 * - `:root` に CSS 変数 (--color-*, --rounded-*, --space-*)
 * - typography はクラス `.type-<name>` として定義（MDX から className="type-h1" 等で使える）
 * - body 全体に base typography と base colors を適用
 */
export function Theme(props: ThemeProps) {
  const {
    name,
    bodyTypography = "body-md",
    bodyColor = "primary",
    bgColor = "neutral",
  } = props;
  const colors = parseMaybeJson(props.colors, {} as Record<string, Color>);
  const typography = parseMaybeJson(props.typography, {} as Record<string, TypographyToken>);
  const rounded = parseMaybeJson(props.rounded, {} as Record<string, Dimension>);
  const spacing = parseMaybeJson(props.spacing, {} as Record<string, Dimension>);
  const fontFamilies = Array.from(
    new Set(
      Object.values(typography)
        .map((t) => t.fontFamily)
        .filter((f): f is string => !!f)
    )
  );
  const fontQuery = fontFamilies
    .map((f) => `family=${encodeURIComponent(f)}:wght@300;400;500;600;700`)
    .join("&");
  const fontsHref = fontQuery
    ? `https://fonts.googleapis.com/css2?${fontQuery}&display=swap`
    : "";

  const colorVars = Object.entries(colors)
    .map(([k, v]) => `    --color-${k}: ${v};`)
    .join("\n");

  const roundedVars = Object.entries(rounded)
    .map(([k, v]) => `    --rounded-${k}: ${dim(v)};`)
    .join("\n");

  const spaceVars = Object.entries(spacing)
    .map(([k, v]) => `    --space-${k}: ${dim(v)};`)
    .join("\n");

  const buildRules = (t: TypographyToken | undefined): string =>
    [
      t?.fontFamily && `font-family: "${t.fontFamily}", system-ui, sans-serif;`,
      t?.fontSize !== undefined && `font-size: ${dim(t.fontSize)};`,
      t?.fontWeight !== undefined && `font-weight: ${t.fontWeight};`,
      t?.lineHeight !== undefined && `line-height: ${dim(t.lineHeight)};`,
      t?.letterSpacing !== undefined && `letter-spacing: ${dim(t.letterSpacing)};`,
    ]
      .filter(Boolean)
      .join("\n      ");

  // `.type-<name>` class (MDX から明示的に付けたい時用)
  const typeClasses = Object.entries(typography)
    .map(([key, t]) => `  .type-${key} {\n      ${buildRules(t)}\n    }`)
    .join("\n");

  // 要素 → typography token のマッピング。Claude の素 HTML でも token が当たる。
  // key は typography map に存在する場合のみ emit する。
  const elementMap: Array<[string, string]> = [
    ["h1", "h1"],
    ["h2", "h2"],
    ["h3", "h3"],
    ["h4", "h3"],
    ["h5", "h3"],
    ["h6", "h3"],
    ["p", "body-md"],
    ["li", "body-md"],
    ["blockquote", "body-md"],
    ["label", "label-sm"],
    ["small", "label-sm"],
    ["figcaption", "label-sm"],
  ];
  const elementDefaults = elementMap
    .filter(([, token]) => typography[token])
    .map(([el, token]) => `    .proposal-root ${el} {\n      ${buildRules(typography[token])}\n    }`)
    .join("\n");

  const baseTypography = typography[bodyTypography];
  const basePrimary = colors[bodyColor] || "#0a0a0a";
  const baseBg = colors[bgColor] || "#ffffff";

  const baseRules = [
    baseTypography?.fontFamily &&
      `font-family: "${baseTypography.fontFamily}", system-ui, sans-serif;`,
    baseTypography?.fontSize !== undefined &&
      `font-size: ${dim(baseTypography.fontSize)};`,
    baseTypography?.lineHeight !== undefined &&
      `line-height: ${dim(baseTypography.lineHeight)};`,
    `color: ${basePrimary};`,
    `background: ${baseBg};`,
  ]
    .filter(Boolean)
    .join("\n      ");

  // spacing.md / spacing.lg / spacing.xl が無い場合の fallback
  const spaceMd = spacing.md ?? "1rem";
  const spaceLg = spacing.lg ?? "2rem";
  const spaceXl = spacing.xl ?? "4rem";

  const css = `
    :root {
${colorVars}
${roundedVars}
${spaceVars}
      --color-text: ${basePrimary};
      --color-bg: ${baseBg};
    }
    .proposal-root {
      ${baseRules}
    }
    .proposal-root h1, .proposal-root h2, .proposal-root h3, .proposal-root h4, .proposal-root h5, .proposal-root h6 {
      color: var(--color-primary, ${basePrimary});
      margin: 0;
    }
    .proposal-root p { margin: 0; }
    .proposal-root ul, .proposal-root ol { margin: 0; padding: 0; }
    .proposal-root a { color: inherit; text-decoration: none; }
    .proposal-root a:hover { text-decoration: underline; text-underline-offset: 0.2em; }
    .proposal-root img { display: block; max-width: 100%; height: auto; }
    .proposal-root blockquote { margin: 0; padding-inline-start: ${dim(spaceMd)}; border-inline-start: 2px solid color-mix(in srgb, var(--color-primary, ${basePrimary}) 30%, transparent); }
    .proposal-root hr { border: 0; border-top: 1px solid color-mix(in srgb, var(--color-primary, ${basePrimary}) 15%, transparent); margin-block: ${dim(spaceLg)}; }
    /* セクション系コンテナの基本姿勢 — className 上書きでいつでも変えられる */
    .proposal-root > section { padding-inline: ${dim(spaceLg)}; padding-block: ${dim(spaceXl)}; }
    @media (min-width: 1024px) {
      .proposal-root > section { padding-inline: ${dim(spaceXl)}; }
    }
${elementDefaults}
${typeClasses}
  `;

  return (
    <>
      {name && <meta name="proposal:name" content={name} />}
      {fontsHref && (
        <>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
          <link rel="stylesheet" href={fontsHref} />
        </>
      )}
      <style dangerouslySetInnerHTML={{ __html: css }} />
    </>
  );
}
