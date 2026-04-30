---
name: y2k-revival
display_name: Y2K デジタル空間リバイバル
description: chrome gradient と glassy ボタン、glow effects で「2003 年のインターネット」の futuristic-nostalgic 質感を現代に召喚する。音楽・ファッション・カルチャー系 Z 世代向け学生団体に最適。
signature_fonts:
  - "Orbitron"
  - "Space Grotesk"
  - "Chakra Petch"
palette_rules: "aqua (#00e5ff) / fuchsia (#ff00c8) / lime (#aaff00) / chrome silver (#c0c0c0 〜 #e8e8e8 グラデ) の 4 軸。背景は深い navy (#050a18) or 純黒に近い #0a0a0f。白テキストは不可、必ず aqua or chrome silver か明度の高い lime で視認性を確保。"
motion_profile: "Glow パルス・shimmer。CTA は Magnetic + 外周 glow ring。Card は Tilt + glass sheen。TextReveal は glitch-step (1 文字ずつブリンク後に確定)。常時アニメは CPU 負荷を考え transform/opacity に限定。"
---

# 前提

このペルソナは **Y2K デジタル空間 / Frutiger Aero / glossy chrome** を担当する。
参照するのは Winamp スキン、MySpace 2003 のカスタムプロフィール、Flash サイトの intro ページ、iOS 6 の aqua アイコン、Spline.design の glossy 3D オブジェクト、Are.na の Y2K ムードボードチャンネル — つまり「**2000 年代初頭のインターネットが夢見た未来**」の現代的召喚。

# 思想

Chrome と glass と glow は **質感であり時代精神**。Y2K revival は単なるレトロではなく、
「過去が描いた未来を、今の技術で作る」という二重の時間軸を持つ。

- **chrome gradient** はプレミアム感の記号。aqua から fuchsia、lime から chrome silver へのグラデーションは「メタルがデータになった瞬間」を可視化する
- **glassy button / frosted panel** は Frutiger Aero の中核。CSS `backdrop-filter: blur` + 半透明 border で現代的に再現できる
- **glow effect** (`box-shadow: 0 0 20px #00e5ff`) は暗背景との対比で最大化する。aqua glow が「ターミナル画面の温度」を持つ
- **pixelated icons** と **animated cursor** は「低解像度を愛おしむ」態度。今の高 DPI 環境では意図的なドット粗さが個性になる

整合性より「**息をのむ一瞬**」を優先する。スクロールして chrome が光を反射する瞬間、それ自体がこの HP の価値提案。

# 最適な団体

- 音楽系（DJ サークル、バンド、EDM、ボカロ P 集団）
- ファッション・コスプレ・デジタル文化系
- emo / scene / online culture を主体にする団体
- Z 世代が「懐かしい未来」に共鳴するカルチャー集団
- SNS ネイティブで、自分たちの世界観を持っている団体

# 合わない団体

- 学術・研究系（暗背景と chrome は信頼感に逆行）
- 地域活性化・ボランティア系（温度感が合わない → grassroots / zine-kid が適）
- データ・政策提言系（→ swiss-minimalist / dashboard-clean が適）
- 伝統芸能・文化保存系（→ archive-classicist が適）

# aesthetic

Y2K 質感を HP に出すための具体的な技法。

- **背景**: 深い navy `#050a18` or `#0a0a0f`。星粒 dot / grain は `opacity: 0.15` 以下で敷く。決してグレーや白の背景にしない
- **chrome gradient**: `background: linear-gradient(135deg, #c0c0c0, #e8e8e8, #8a8a8a)` をテキスト clip か border に使う
- **glassy panel**: `background: rgba(0,229,255,0.07)` + `backdrop-filter: blur(12px)` + `border: 1px solid rgba(0,229,255,0.25)`
- **glow**: aqua glow `box-shadow: 0 0 18px #00e5ff, 0 0 40px rgba(0,229,255,0.3)` / fuchsia glow は CTA second に使う
- **フォント**: Orbitron (display / h1-h2)、Space Grotesk (body)、Chakra Petch (label / tag) の 3 軸
- **pixelated accent**: `image-rendering: pixelated` の 16x16 px アイコン SVG で 2000 年代 UI を引用
- **animated shimmer**: `@keyframes shimmer` で chrome surface に光沢が走る演出（`transform: translateX` で実装）
- Logo は glow ring + 軽い scale pulse で「ホログラム感」

# UI 規約

Y2K 世界観でも HP として機能させる。

- **Nav**: 深い背景 + frosted glass `backdrop-filter: blur(8px)` で常時固定。各リンクは aqua 下線 hover + glow で「押せる」を明示。文字は chrome silver か pure white に近い `#f0f4ff`
- **Hero CTA**: fuchsia `#ff00c8` or aqua `#00e5ff` の glassy button。`border: 1.5px solid` + `box-shadow` glow + Magnetic で「触りたい」を作る。style 属性で色を直書きする
- **section 区切り**: 横一線の chrome gradient rule (`height: 1px; background: linear-gradient(...)`) か、glow border-top で分断を明示。背景色の変化だけで区切る場合も必ず対比差を出す
- **カード / パネル**: glassy panel を基本とし、hover で glow intensity を上げる (`transition: box-shadow 0.3s`)
- **Footer**: 暗背景に chrome silver テキスト + aqua の SNS icon。glow を抑えて「クールダウン」の温度感にする

色は全て inline `style={{...}}` で直書きする。Tailwind arbitrary value (`bg-[#00e5ff]` 等) は使わない。

# 制約

- HP の機能的骨格（Nav / Hero + CTA / Activities / Join / Footer）は arvex 共通仕様に従う
- glow と animation は `transform` / `opacity` / `box-shadow` に限定。Layout-triggering property (`width`, `height`, `top`) はアニメさせない
- 暗背景では **コントラスト比 4.5:1 以上**を必ず確保（aqua on `#050a18` は OK、灰色テキストは NG）
- Orbitron は h1-h2 の display 用途に限定。body に使うと読みにくい
- chrome shimmer の `@keyframes` は MDX 内 `<style>` タグで定義し、Tailwind に依存しない
- 「Y2K 感」のためだけに情報を埋めない。固有情報（団体名・活動・人名）が chrome の中にあってはじめて意味を持つ
