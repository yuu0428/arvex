type Color = string;
type Dimension = string | number;

type TypographyToken = {
  fontFamily?: string;
  fontSize?: Dimension;
  fontWeight?: number | string;
  lineHeight?: Dimension;
  letterSpacing?: Dimension;
};

type ThemeProps = {
  name?: string;
  /** DESIGN.md colors map (primary, secondary, ...). CSS var --color-<name> */
  colors?: Record<string, Color>;
  /** DESIGN.md typography map (h1, body-md, label-sm, ...). Emits .type-<name> class */
  typography?: Record<string, TypographyToken>;
  /** rounded: xs/sm/md/lg/xl/full → --rounded-<name> */
  rounded?: Record<string, Dimension>;
  /** spacing: xs/sm/md/lg/xl → --space-<name> */
  spacing?: Record<string, Dimension>;
  /** ページ全体の base 値 */
  bodyTypography?: string; // typography key を指定（例: "body-md"）
  bodyColor?: string; // colors key
  bgColor?: string; // colors key
};

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
export function Theme({
  name,
  colors = {},
  typography = {},
  rounded = {},
  spacing = {},
  bodyTypography = "body-md",
  bodyColor = "primary",
  bgColor = "neutral",
}: ThemeProps) {
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

  const typeClasses = Object.entries(typography)
    .map(([key, t]) => {
      const rules = [
        t.fontFamily && `font-family: "${t.fontFamily}", system-ui, sans-serif;`,
        t.fontSize !== undefined && `font-size: ${dim(t.fontSize)};`,
        t.fontWeight !== undefined && `font-weight: ${t.fontWeight};`,
        t.lineHeight !== undefined && `line-height: ${dim(t.lineHeight)};`,
        t.letterSpacing !== undefined && `letter-spacing: ${dim(t.letterSpacing)};`,
      ]
        .filter(Boolean)
        .join("\n      ");
      return `  .type-${key} {\n      ${rules}\n    }`;
    })
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
    .proposal-root h1, .proposal-root h2, .proposal-root h3, .proposal-root h4 {
      color: var(--color-primary, ${basePrimary});
    }
    .proposal-root a { color: inherit; }
    .proposal-root img { display: block; max-width: 100%; height: auto; }
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
