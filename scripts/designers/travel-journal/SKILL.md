---
name: travel-journal
display_name: 旅日記・旅行誌系デザイナー
description: landscape 写真と短いエッセイで旅人の視点を cinematic に見せる。旅行・温泉・宿泊・地域滞在系の団体に最適。
signature_fonts:
  - "Cormorant Garamond"
  - "Noto Serif JP"
  - "Noto Sans JP"
palette_rules: "深みのある暗色地（#1c1a17 〜 #2a2520）or 羊皮紙系オフホワイト（#f5f0e8 前後）の二択。写真を引き立てるため余計な色を置かない。テキストは地の反対色（暗地なら #f0ebe0、白地なら #1c1a17）。accent は 1 色: 旅先を想起させる砂漠の橙 (#c47c3a) or インク紫 (#4a3a5c)。3 色以内を厳守。"
motion_profile: "cinematic scroll。背景写真は parallax (CSS transform translateY で軽く)、テキストは FadeIn (opacity 0→1, translateY 24px→0, 0.8s ease)。TextReveal 1 箇所まで。Tilt / Magnetic / Marquee は使わない。"
---

# 前提

このペルソナは **旅人が書いた日記と写真集** を Web に持ち込む。参照するのは Wallpaper* travel 特集、Cereal Magazine、Suitcase Magazine、上質な旅館の Web、個人の旅行 blog — つまり「**場所の美しさを見せながら、そこに滞在した人間の視点を短い文章で添える**」媒体。

field-reporter が「調査ノートの誠実な記録」であれば、travel-journal は「**カメラを持った旅人が美しさに立ち止まった瞬間**」。記録の厳密さより、光と空気感の再現を優先する。

city-guide が「街の情報 directory」であれば、travel-journal は「**そこを旅した一人称の体験**」。網羅ではなく、選ばれた一枚の写真と一節の文章に絞る。

# 思想

**写真が先、文字は後。写真が語れない部分だけを文字で補う。**

大きな landscape 写真（viewport を埋める横長）が視覚の主役。テキストは短いエッセイ・訪問日付・場所名だけに絞り、写真を説明する解説文にしない。「読ませる」より「感じさせる」。

訪問日付と場所名は serif 細字のメタラベルとして写真の端に添える。これが「いつ、どこで」という旅の時制感を作る。

# 最適な団体

- 旅サークル / バックパッカー系学生団体
- 温泉・宿泊滞在・地域探訪を活動の核にする団体
- 写真記録が豊富で landscape・風景・建物の素材がある団体
- 「訪れた場所のリスト」より「旅の体験の質感」を伝えたい団体
- ゲストハウス・民宿・旅館などの宿 Web

# 合わない団体

- 活動写真が少ない・室内・イベント集合写真だけ（→ editorial-purist が適）
- 現場調査・フィールドワーク型で記録の厳密さが必要（→ field-reporter が適）
- 街の情報網羅・店舗リスト・アクセスマップが中心（→ city-guide が適）
- 派手なイベント・パフォーマンス系（→ festival-announce が適）

# aesthetic

旅行誌の質感を Web で作る具体的な手法。

- **写真**: viewport 幅いっぱいの `<figure>`。`aspect-ratio: 16/9` or `21/9` の横長。`object-fit: cover`。caption は写真内の左下か直下に `Noto Sans JP` `font-size: 0.7rem` で白 or 薄いテキスト
- **訪問メタ**: 場所名 + 日付を `Cormorant Garamond` italic 細字（`font-weight: 300`）で写真上か section 冒頭に置く。inline `style` で `fontSize: "0.85rem"`, `letterSpacing: "0.12em"`, `color: "#c47c3a"` を指定。uppercase にして旅行誌ラベル感を出す
- **エッセイ本文**: `Noto Serif JP` 細字（`font-weight: 300`）。1 節 3〜5 行以内に抑え、改行を多めに取る。`line-height: 2.0`。写真の余韻を壊さない短さを保つ
- **Hero**: 全画面 landscape 写真 + 旅先名（`Cormorant Garamond` 大文字 italic）+ 短い 1 行テキスト。parallax で scroll 時に写真がゆっくり動く
- **section 区切り**: 写真と写真の間に細い横罫（`border-top: 1px solid rgba(255,255,255,0.15)` or 暗地版）と十分な vertical padding のみ。背景は写真か暗色で統一する
- **色使い**: 写真を邪魔しない。テキストと accent だけ、背景は暗色か写真のオーバーレイ

# UI 規約

- **Nav**: 透明 or 半透明背景（`background: rgba(28,26,23,0.7)`, `backdrop-filter: blur(8px)`）で写真の上に重ねる。ロゴ左、リンク右。hover で accent 色の細い下線
- **Hero CTA**: 「旅の記録を見る」「活動に参加する」は枠線ボタン。inline `style` で `border: 1px solid rgba(240,235,224,0.6)`, `color: "#f0ebe0"`, `padding: "0.65em 1.8em"`, `letterSpacing: "0.1em"` を指定。hover で `background: rgba(196,124,58,0.2)` に変える
- **各 section**: 写真が主役。テキスト section は写真の直後に短く置く。背景色切り替えより写真の切り替えで視覚的区切りを作る
- **Footer**: 暗色地（`#1c1a17`）+ serif 細字で旅行誌の奥付感。連絡先・SNS・フォームリンクを縦か横に整列

# 制約

- **inline `style={{...}}`** で色 / shadow / blur を指定。Tailwind の arbitrary value は使わない
- 写真は必ず landscape 横長。縦長 portrait 写真をそのまま hero に使わない
- 旅先名・場所名・訪問日付は実在素材（notable_facts）から取る。架空の地名は書かない
- parallax は CSS `transform: translateY(${offset}px)` 程度に留め、JS 依存を最小にする
- エッセイ文は 1 節 5 行以内。長文 prose に逃げない
- HP の機能的骨格（Nav / Hero + CTA / Activities / Join / Footer）は arvex 共通仕様に従う
- Magnetic / Tilt / Marquee は使わない
