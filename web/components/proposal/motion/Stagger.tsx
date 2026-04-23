"use client";

import { motion, useInView } from "motion/react";
import { useRef, Children, ReactNode, isValidElement } from "react";

type StaggerProps = {
  children: ReactNode;
  delay?: number;
  distance?: number;
};

/** 子要素を順番に表出させる。MDX の whitespace テキストノードはスキップ。 */
export function Stagger({ children, delay = 0.14, distance = 48 }: StaggerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });

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
        visible: { transition: { staggerChildren: delay } },
      }}
    >
      {items.map((child, i) => (
        <motion.div
          key={i}
          variants={{
            hidden: { opacity: 0, y: distance },
            visible: { opacity: 1, y: 0 },
          }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        >
          {child}
        </motion.div>
      ))}
    </motion.div>
  );
}
