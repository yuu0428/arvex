import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "arvex — HPで、活動を伝わる形に。",
  description:
    "学生団体・サークル専用のホームページ制作サービス。1枚4,000円から、最短即日。",
  openGraph: {
    title: "arvex — HPで、活動を伝わる形に。",
    description:
      "学生団体・サークル専用のホームページ制作サービス。1枚4,000円から、最短即日。",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ja"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
