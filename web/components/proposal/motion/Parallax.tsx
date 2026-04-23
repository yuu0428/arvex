"use client";

import { motion, useScroll, useTransform, useReducedMotion } from "motion/react";
import { useRef, ReactNode } from "react";

type ParallaxProps = {
  children: ReactNode;
  speed?: number; // -1..1。正で下方向、負で上方向に translate
};

/** 対象要素のスクロール進捗に bind した translate。subtle に使うのが良い。 */
export function Parallax({ children, speed = 0.3 }: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const reduce = useReducedMotion();
  const clamp = Math.max(-1, Math.min(1, speed));
  const y = useTransform(scrollYProgress, [0, 1], [`${-clamp * 80}px`, `${clamp * 80}px`]);

  return (
    <motion.div ref={ref} style={reduce ? undefined : { y }}>
      {children}
    </motion.div>
  );
}
