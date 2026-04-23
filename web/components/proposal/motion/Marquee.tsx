"use client";

import { motion } from "motion/react";
import { ReactNode } from "react";

type MarqueeProps = {
  children: ReactNode;
  direction?: "left" | "right";
  speed?: "slow" | "medium" | "fast";
  gap?: number;
};

const DURATION = { slow: 40, medium: 24, fast: 14 };

/** 無限スクロール帯。 */
export function Marquee({
  children,
  direction = "left",
  speed = "medium",
  gap = 64,
}: MarqueeProps) {
  const duration = DURATION[speed];
  const target = direction === "left" ? "-50%" : "50%";

  const item = (
    <span style={{ display: "inline-block", paddingRight: gap }}>{children}</span>
  );

  return (
    <div style={{ overflow: "hidden", whiteSpace: "nowrap" }}>
      <motion.div
        style={{ display: "inline-block" }}
        animate={{ x: target }}
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
