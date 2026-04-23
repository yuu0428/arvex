"use client";

import { motion, useReducedMotion } from "motion/react";
import { ReactNode } from "react";

type MarqueeProps = {
  children: ReactNode;
  direction?: "left" | "right";
  speed?: "slow" | "medium" | "fast";
  gap?: number; // px
};

const DURATION = { slow: 40, medium: 24, fast: 14 };

/** 無限スクロール帯。h1 の脇役や section divider に。 */
export function Marquee({
  children,
  direction = "left",
  speed = "medium",
  gap = 64,
}: MarqueeProps) {
  const reduce = useReducedMotion();
  const duration = DURATION[speed];
  const target = direction === "left" ? "-50%" : "50%";

  const item = (
    <span style={{ display: "inline-block", paddingRight: gap }}>{children}</span>
  );

  return (
    <div style={{ overflow: "hidden", whiteSpace: "nowrap" }}>
      <motion.div
        style={{ display: "inline-block" }}
        animate={reduce ? undefined : { x: target }}
        transition={{ duration, ease: "linear", repeat: Infinity }}
        initial={{ x: 0 }}
      >
        {item}
        {item}
        {item}
        {item}
      </motion.div>
    </div>
  );
}
