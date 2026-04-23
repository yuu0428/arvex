"use client";

import { MotionConfig } from "motion/react";
import { ReactNode } from "react";

/**
 * 提案ページ配下の motion/react アニメーションを一括設定する root。
 *
 * - `reducedMotion="user"`: ユーザーの `prefers-reduced-motion: reduce` 設定を
 *   尊重。reduce なら全アニメーションが瞬時に終了する（個別部品で
 *   `useReducedMotion` を判定する必要がなくなる）
 */
export function MotionRoot({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
