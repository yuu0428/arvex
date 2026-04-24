# モックアップ → コード実装: 2026 年の state of the art

## 1. 典型的な失敗パターンと回避策

### 1.1 要素の欠落・歪み・位置ずれ（Element Omission / Distortion / Misarrangement）

FSE 2025 採択の DCGen 論文（arxiv 2406.16386）は、マルチモーダル LLM がスクリーンショットを一括処理する場合の失敗を 3 種類に分類している。

| 失敗種別 | 説明 | 出現傾向 |
|---|---|---|
| Element Omission | UI 要素が生成コードから丸ごと消える | 画像が大きく情報密度が高い場合 |
| Element Distortion | ボタンや画像のサイズ・比率が変わる | グラデーション・シャドウなど視覚的に複雑な要素 |
| Element Misarrangement | 要素の配置・順序がずれる | グリッド・絶対配置が混在するレイアウト |

**回避策**: DCGen の分割統治アプローチを採用する。画像をセマンティックな単位（セクション）に分割し、セグメントごとにコードを生成してから結合する。大画像で視覚類似度 +15%、コード類似度 +8% の改善が実証されている。

### 1.2 絶対配置地獄（Absolute Positioning Hell）

Figma Make（2025 年リリース）は視覚的な再現精度は高いが、Figma レイヤーを absolute positioning でそのままコードに変換するため、レスポンシブ非対応かつ保守不能なコードになる。

**回避策**:
- Figma Make はビジュアル確認用プロトタイプとしてのみ使う
- 実装コードは v0 や Lovable など prompt-first ツールで別途生成する
- 生成後に「Flexbox / Grid に変換してレスポンシブ対応してください」と続けてリファインする

### 1.3 グラデーション・CSS 特殊表現の再現失敗

LLM は `radial-gradient()` や `backdrop-filter`、複雑な CSS アニメーションを画像から推定することが苦手。

**回避策**:
- グラデーションは `--color-primary: #1a2b3c` のように HEX 値をプロンプトに明示する
- Tailwind クラス名で指定する（`from-purple-600 to-pink-500` 等）
- アニメーションは「framer-motion の fadeInUp を 0.4s で適用」と効果レベルで指示する

### 1.4 タイポグラフィの不一致

モデルは訓練データの統計的傾向から「よく使われるフォント」（Space Grotesk、Inter 等）に引っ張られる。

**回避策**:
- フォント名・ウェイト・サイズ（px または rem）をプロンプトで明示する
- モックアップを「雰囲気で参照」させるのではなく仕様として渡す

### 1.5 レイアウト比率のズレ

スクリーンショット内の余白（padding/margin）を LLM がピクセルから推定する際に誤差が大きくなる。

**回避策**:
- 「カード間 gap-6（24px）、セクション上下 py-16（64px）」と数値で指示する
- DOM ツリー構造を先に決めてから数値を埋める

---

## 2. プロンプティング best practice

### 2.1 二段階アプローチ（最強）

**Step 1: モックアップから設計仕様を抽出 → Step 2: 仕様を渡してコードを生成** の分離。

Step 1 で JSON 抽出（色・セクション・タイポ・スペーシング）、Step 2 でその JSON + ストラクチャ要件からコード生成。

### 2.2 v0 のベストプラクティス

- 高解像度のスクリーンショットを使う
- 全体ではなく「ヒーロー部分だけ」「カード 1 枚だけ」に切り出してアップロード
- 「このモックアップに近いコードを書いて」ではなく「こういう挙動と構造にしてほしい」と機能も言葉で補足

### 2.3 具体値 vs 雰囲気 match

| アプローチ | 向く場面 |
|---|---|
| HEX / px 値を明示 | デザインシステムが固まっている、既存デザインを忠実に再現したい |
| 雰囲気 match | 素早いプロトタイプ、提案フェーズでデザイン方向性を試したい |

**学生団体向け HP の提案フェーズ**は雰囲気 match で十分。

### 2.4 コンポーネント単位で分割

v0 公式、Figma Make レビュー、DCGen 論文の三方が共通して指摘: **大きな画像を一括処理させない**。

- Nav → Hero → Features → CTA → Footer と分割
- 各セクションを独立したプロンプトで生成
- 最後に「これらを組み合わせて 1 ページにしてください」と統合

### 2.5 イテレーション前提

> 「生成 → 1〜2 点の具体的な修正 → 送信」サイクルを繰り返す。一度に大量の要求を投げない。（v0 プロンプティングガイド）

---

## 3. モックアップの質 vs コード品質

### 3.1 高精細モックアップは両刃の剣

| モックアップの種類 | LLM のコード精度 | 注意点 |
|---|---|---|
| 低忠実度ワイヤーフレーム | レイアウト構造は把握しやすい、色・フォントは推定不可 | 雰囲気指定を別途付ける必要あり |
| 中忠実度モックアップ | バランスが良い。構造・余白・主要色が読み取れる | **最も ROI が高い** |
| 高精細 AI 生成画像 | グラデーションや微妙なシャドウも入るが CSS で再現できない | 視覚ターゲットとして使い、具体値は別途指定 |

### 3.2 解像度と精度の関係

- DCGen 実験: 「大きな画像ほど欠落と歪みが増える」
- 分割すると改善するが、過剰に細かいと組み立て時の整合性が崩れる
- **実用的な粒度: セクション単位**

### 3.3 AI 生成画像を視覚ターゲットにする場合

1. 画像生成ツール（Codex / Midjourney / Flux）でビジュアルイメージを作る
2. Step 1 プロンプトで色・レイアウト・フォント仕様を JSON 抽出する
3. 抽出した JSON と画像 URL を同時に渡してコード生成する
4. 「このイメージに似せつつ Tailwind の標準クラスで再現してください」と明示

---

## 4. 複数モックアップの扱い

### 4.1 デスクトップ + モバイル

1. デスクトップ版モックアップでコード生成（skeleton）
2. 「sm ブレークポイント以下でこのモバイルモックアップのレイアウトにしてください」と画像を追加
3. Tailwind の responsive prefix が正しく入るか確認

### 4.2 複数セクションを統合する場合

MLS（Modular Layout Synthesis, arxiv 2512.18996）:
- セクションごとに生成したコードを単純結合すると「モノリシック flat ファイル」になる
- **対策**: 先にコンポーネント型定義を決めてから各セクションを生成
- または「共通コンポーネントを抽出してリファクタ」を追加ターンで指示

### 4.3 デザインシステムを先に定義（v0 公式推奨）

1. Button・Card・Badge など基礎コンポーネントを先にモックアップ画像から生成
2. それらの React コンポーネントを確定
3. 「このコンポーネント群を使って Hero セクションを組んでください」と指示

---

## 5. arvex 向け推奨

### 5.1 現状パイプラインの課題

画像を Claude に「雰囲気で見て」渡すと失敗パターン（グラデーション・フォント・スペーシング）が発生しやすい。

### 5.2 推奨追加: Stage 2.5（仕様 JSON 抽出）

```text
Stage 2.5: Codex 生成画像 → 設計仕様 JSON 抽出

Codex 生成画像（Blob URL）を Claude に渡して以下を抽出:
{
  "color_palette": { "primary": "#...", "accent": "#...", "bg": "#..." },
  "sections": ["hero", "features", "pricing", "cta"],
  "typography": {
    "heading": "font-bold text-4xl tracking-tight",
    "body": "text-base leading-relaxed"
  },
  "spacing": {
    "section_padding": "py-16 px-6",
    "card_gap": "gap-6"
  }
}
```

**追加コスト**: Claude 1 往復（5〜15 秒）= 現在の前処理として吸収可能。

### 5.3 モックアップ生成の品質戦略

| 用途 | 推奨品質 | 理由 |
|---|---|---|
| 顧客への提案送付 | 高精細（Codex / Flux 相当） | 「こんなサイトが作れます」を視覚的に示す |
| コード生成の視覚ターゲット | 中精細 + JSON 仕様 | LLM が CSS で再現できる範囲に収める |

→ **2 種類のモックアップを使い分ける**

### 5.4 コスト・スピードのトレードオフ

| 方式 | 追加コスト | コード精度向上 | 推奨度 |
|---|---|---|---|
| 現状（画像を見て直接 HTML 生成） | なし | ベースライン | 現在 |
| **Stage 2.5 で JSON 仕様抽出を追加** | Claude 1 往復（+5〜15 秒） | 高 | **推奨** |
| セクション分割して各々生成 | 往復数が 3〜5 倍 | 最高 | 大規模 HP のみ |

### 5.5 4000 円 / ページの単価感との整合

- 1 ページ 4000 円では人手介在コストを最小化する必要がある
- Stage 2.5 の JSON 抽出追加は**完全自動で実装可能** → ROI 最高
- セクション分割生成は手作業が増えるため現時点では見送り
- 将来の 15000 円プラン（10 枚）に移行したタイミングで DCGen 的な分割統治を検討

---

## 参考ソース

- [DCGen: Divide-and-Conquer Approach for UI Code Generation (FSE 2025)](https://arxiv.org/abs/2406.16386)
- [Design2Code: Benchmarking Multimodal Code Generation (NAACL 2025)](https://aclanthology.org/2025.naacl-long.199.pdf)
- [WebSight Dataset: Unlocking Web Screenshots into HTML (HuggingFace Blog)](https://huggingface.co/blog/websight)
- [Waffle: Fine-tuning Multi-Modal Models for Front-End Dev (ACL 2025)](https://arxiv.org/html/2410.18362)
- [MLS: Modular Layout Synthesis (arxiv 2512.18996)](https://arxiv.org/abs/2512.18996)
- [Figma Make: closer, but not there yet](https://annaarteeva.medium.com/figma-make-closer-but-not-there-yet-6ee5418fdbcc)
- [v0 vs Figma Make Compared (Codivox)](https://codivox.com/v0-vs-figma-make/)
- [Working with Figma in v0 (Vercel Blog)](https://vercel.com/blog/working-with-figma-and-custom-design-systems-in-v0)
- [v0 Screenshots Docs](https://v0.app/docs/screenshots)
- [Screenshot to Code: Lovable vs v0 vs Bolt (AImultiple)](https://aimultiple.com/screenshot-to-code)
- [abi/screenshot-to-code (GitHub)](https://github.com/abi/screenshot-to-code)
- [Improving frontend design through Skills (Anthropic Blog)](https://claude.com/blog/improving-frontend-design-through-skills)
