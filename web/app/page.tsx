import Image from "next/image";

const BASE = process.env.NODE_ENV === "production" ? "/arvex" : "";
const asset = (p: string) => `${BASE}${p}`;

const PRICING = [
  { pages: "1ページ", price: "4,000円", note: "最低プラン" },
  { pages: "2ページ", price: "7,000円", note: "2枚目 +3,000円" },
  { pages: "3ページ", price: "9,000円", note: "3枚目以降 +2,000円" },
  { pages: "5ページ", price: "13,000円", note: "" },
  { pages: "特別プラン", price: "15,000円", note: "10ページまで定額" },
  { pages: "独自ドメイン", price: "2,000円 / 年", note: "サブスク" },
];

const FLOW = [
  { step: "01", title: "ヒアリング", body: "活動内容・目的・想いを伺います。数分のやり取りでOK。" },
  { step: "02", title: "たたき台HPの提示", body: "実際に動くデモHPを作ってお見せします。" },
  { step: "03", title: "修正・仕上げ", body: "ご要望をもとに調整。写真や文章は任せていただいてOK。" },
  { step: "04", title: "公開", body: "独自ドメインの設定・公開まで対応します。" },
];

const FAQ = [
  {
    q: "なぜこんなに安いんですか？",
    a: "制作の多くを自動化しているからです。学生団体の皆さんが予算を気にせず頼めるラインを設計しました。",
  },
  {
    q: "何日くらいで作れますか？",
    a: "最短即日、通常は2〜3日で初稿をお見せします。",
  },
  {
    q: "公開後の修正はできますか？",
    a: "軽微な修正は無料で対応します。大幅な構成変更は追加ページとして扱います。",
  },
  {
    q: "独自ドメインは必要ですか？",
    a: "必須ではありません。arvexが用意するサブドメインでも公開できます。",
  },
];

const TEAM = [
  { role: "CEO", name: "渡邊 悠斗", en: "Yuto Watanabe" },
  { role: "COO", name: "末松 結楽", en: "Yura Suematsu" },
  { role: "CIO", name: "金丸 雄樹", en: "Yuki Kanamaru" },
];

export default function Home() {
  return (
    <>
      {/* Hero — dark */}
      <header className="bg-[#0a0a0a] text-white">
        <nav className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
          <Image
            src={asset("/brand/logo-horizontal.png")}
            alt="arvex"
            width={120}
            height={32}
            className="invert brightness-0"
            priority
          />
          <div className="hidden sm:flex gap-8 text-sm text-white/70">
            <a href="#service" className="hover:text-white transition">サービス</a>
            <a href="#pricing" className="hover:text-white transition">料金</a>
            <a href="#flow" className="hover:text-white transition">制作の流れ</a>
            <a href="#team" className="hover:text-white transition">チーム</a>
            <a href="#contact" className="hover:text-white transition">お問い合わせ</a>
          </div>
        </nav>

        <div className="max-w-6xl mx-auto px-6 pt-24 pb-32 sm:pt-32 sm:pb-40 text-center">
          <Image
            src={asset("/brand/logo-dark.png")}
            alt="arvex"
            width={220}
            height={220}
            className="mx-auto mb-12 opacity-95"
            priority
          />
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight leading-tight">
            HPで、<br className="sm:hidden" />
            活動を伝わる形に。
          </h1>
          <p className="mt-8 text-white/70 text-lg max-w-xl mx-auto leading-relaxed">
            学生団体・サークル専用のホームページ制作。<br />
            1ページ4,000円から、最短即日で公開まで。
          </p>
          <div className="mt-12 flex gap-4 justify-center flex-wrap">
            <a
              href="#contact"
              className="px-8 py-4 bg-white text-black font-medium rounded-full hover:bg-white/90 transition"
            >
              お問い合わせ
            </a>
            <a
              href="#pricing"
              className="px-8 py-4 border border-white/30 text-white font-medium rounded-full hover:bg-white/10 transition"
            >
              料金を見る
            </a>
          </div>
        </div>
      </header>

      {/* Service */}
      <section id="service" className="bg-white py-24 sm:py-32">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-sm tracking-widest text-black/50 mb-4">SERVICE</p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-16">
            学生団体のための、<br />
            最短ホームページ制作。
          </h2>
          <div className="grid sm:grid-cols-3 gap-10">
            <div>
              <div className="w-12 h-12 border border-black rounded-full flex items-center justify-center mb-6 font-mono">01</div>
              <h3 className="font-bold text-lg mb-3">圧倒的に安い</h3>
              <p className="text-black/70 leading-relaxed text-sm">
                1ページ4,000円から。10ページ定額プランも15,000円。学生団体の予算感に徹底的に寄り添った価格設計。
              </p>
            </div>
            <div>
              <div className="w-12 h-12 border border-black rounded-full flex items-center justify-center mb-6 font-mono">02</div>
              <h3 className="font-bold text-lg mb-3">最短即日</h3>
              <p className="text-black/70 leading-relaxed text-sm">
                制作フローを自動化しているため、ヒアリングから初稿提示までが極端に速い。新歓・イベント前の駆け込みも対応。
              </p>
            </div>
            <div>
              <div className="w-12 h-12 border border-black rounded-full flex items-center justify-center mb-6 font-mono">03</div>
              <h3 className="font-bold text-lg mb-3">伝わる設計</h3>
              <p className="text-black/70 leading-relaxed text-sm">
                集客・信用・募集など、目的に合わせた構成を提案。ただのデザインではなく、成果につながる見せ方を一緒に考えます。
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="bg-[#f7f7f5] py-24 sm:py-32">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-sm tracking-widest text-black/50 mb-4">PRICING</p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-4">
            分かりやすい、<br className="sm:hidden" />一枚単位の料金。
          </h2>
          <p className="text-black/60 mb-16 leading-relaxed">
            ページが増えるほど1枚あたりが安くなる設計です。
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {PRICING.map((p) => (
              <div
                key={p.pages}
                className="bg-white border border-black/10 rounded-2xl p-8 hover:border-black transition"
              >
                <p className="text-sm text-black/50">{p.pages}</p>
                <p className="text-3xl font-bold mt-2">{p.price}</p>
                {p.note && <p className="text-xs text-black/40 mt-2">{p.note}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Flow */}
      <section id="flow" className="bg-white py-24 sm:py-32">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-sm tracking-widest text-black/50 mb-4">FLOW</p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-16">
            制作の流れ。
          </h2>
          <div className="space-y-12">
            {FLOW.map((f) => (
              <div key={f.step} className="flex gap-8 items-start border-b border-black/10 pb-12 last:border-b-0">
                <div className="font-mono text-2xl text-black/30 w-20 shrink-0">{f.step}</div>
                <div>
                  <h3 className="text-xl font-bold mb-2">{f.title}</h3>
                  <p className="text-black/70 leading-relaxed">{f.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-[#f7f7f5] py-24 sm:py-32">
        <div className="max-w-3xl mx-auto px-6">
          <p className="text-sm tracking-widest text-black/50 mb-4">FAQ</p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-16">
            よくある質問。
          </h2>
          <div className="space-y-8">
            {FAQ.map((item) => (
              <div key={item.q} className="border-b border-black/10 pb-8 last:border-b-0">
                <h3 className="font-bold text-lg mb-3">Q. {item.q}</h3>
                <p className="text-black/70 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Team */}
      <section id="team" className="bg-white py-24 sm:py-32">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-sm tracking-widest text-black/50 mb-4">TEAM</p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-16">
            つくっている人。
          </h2>
          <div className="grid sm:grid-cols-3 gap-8">
            {TEAM.map((m) => (
              <div key={m.role} className="border border-black/10 rounded-2xl p-8">
                <p className="font-mono text-xs text-black/40 tracking-widest">{m.role}</p>
                <p className="text-2xl font-bold mt-4">{m.name}</p>
                <p className="text-sm text-black/50 mt-1">{m.en}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact */}
      <section id="contact" className="bg-[#0a0a0a] text-white py-24 sm:py-32">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <p className="text-sm tracking-widest text-white/50 mb-4">CONTACT</p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight mb-8">
            まずは、お話ししましょう。
          </h2>
          <p className="text-white/70 mb-12 leading-relaxed">
            ご相談・お見積もり・細かい質問、なんでもお気軽に。
          </p>
          <a
            href="mailto:hello@example.arvex.jp"
            className="inline-block px-10 py-5 bg-white text-black font-medium rounded-full hover:bg-white/90 transition"
          >
            hello@example.arvex.jp
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#0a0a0a] text-white/40 border-t border-white/10 py-10">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between text-sm">
          <Image
            src={asset("/brand/logo-horizontal.png")}
            alt="arvex"
            width={80}
            height={22}
            className="invert brightness-0 opacity-50"
          />
          <p>© 2026 arvex</p>
        </div>
      </footer>
    </>
  );
}
