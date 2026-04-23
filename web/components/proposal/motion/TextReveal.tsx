"use client";

import { motion, useInView } from "motion/react";
import { useRef, ReactNode } from "react";

type TextRevealProps = {
  children: ReactNode;
  by?: "word" | "char";
  delay?: number;
  stagger?: number;
};

/** 文字列を単語/文字単位で下から表出。SSR/CSR で必ず同じ分割結果を描画する。
 *  children が string でない場合（React 要素など）はそのまま出す（保険）。 */
export function TextReveal({
  children,
  by = "word",
  delay = 0,
  stagger = 0.05,
}: TextRevealProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-30px" });

  if (typeof children !== "string") {
    return <span ref={ref}>{children}</span>;
  }

  const segments =
    by === "char" ? Array.from(children) : children.split(/(\s+)/);

  return (
    <span ref={ref} style={{ display: "inline-block" }}>
      {segments.map((seg, i) =>
        seg.trim() === "" ? (
          <span key={i}>{seg}</span>
        ) : (
          <motion.span
            key={i}
            style={{ display: "inline-block", willChange: "transform, opacity" }}
            initial={{ opacity: 0, y: "90%" }}
            animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: "90%" }}
            transition={{
              duration: 0.7,
              delay: delay + i * stagger,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {seg}
          </motion.span>
        ),
      )}
    </span>
  );
}
