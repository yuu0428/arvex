import { ReactNode } from "react";

type ProseProps = {
  children: ReactNode;
};

/**
 * 長めのテキストを読みやすく整える。MDX の地の文 (p, ul, li, strong, em) に
 * ちょうどいいタイポグラフィを与える。
 */
export function Prose({ children }: ProseProps) {
  return (
    <div className="max-w-2xl leading-relaxed [&>p]:mb-4 [&>ul]:list-disc [&>ul]:pl-6 [&>ul]:mb-4 [&_a]:underline">
      {children}
    </div>
  );
}
