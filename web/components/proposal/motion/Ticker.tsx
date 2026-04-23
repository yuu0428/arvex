"use client";

import { animate, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

type TickerProps = {
  from?: number;
  to: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
};

/** viewport 入りで数字を from から to までカウントアップする。
 *  初期表示は常に from なので SSR/CSR でマークアップが一致する。 */
export function Ticker({ from = 0, to, duration = 1.4, prefix, suffix }: TickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [value, setValue] = useState(from);

  useEffect(() => {
    if (!inView) return;
    const controls = animate(from, to, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setValue(Math.round(v)),
    });
    return () => controls.stop();
  }, [inView, from, to, duration]);

  return (
    <span ref={ref}>
      {prefix}
      {value.toLocaleString()}
      {suffix}
    </span>
  );
}
