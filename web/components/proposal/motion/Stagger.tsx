"use client";

import { motion, useInView, useReducedMotion } from "motion/react";
import { useRef, Children, ReactNode, isValidElement } from "react";

type StaggerProps = {
  children: ReactNode;
  delay?: number; // children 間の遅延（秒）
  distance?: number;
};

/** 子要素を順番に表出させる。MDX の whitespace テキストノードはスキップ。 */
export function Stagger({ children, delay = 0.14, distance = 48 }: StaggerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();

  const items = Children.toArray(children).filter(
    (c) => !(typeof c === "string" && c.trim() === "") && isValidElement(c),
  );

  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={inView ? "visible" : "hidden"}
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: reduce ? 0 : delay } },
      }}
    >
      {items.map((child, i) => (
        <motion.div
          key={i}
          variants={{
            hidden: reduce ? { opacity: 0 } : { opacity: 0, y: distance },
            visible: { opacity: 1, y: 0 },
          }}
          transition={{ duration: reduce ? 0 : 0.9, ease: [0.22, 1, 0.36, 1] }}
        >
          {child}
        </motion.div>
      ))}
    </motion.div>
  );
}
