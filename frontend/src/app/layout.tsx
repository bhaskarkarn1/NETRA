import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/shared/navbar";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NETRA — Digital Public Safety Intelligence",
  description:
    "AI-powered platform for scam detection, fraud network investigation, and citizen inoculation against digital threats.",
  keywords: [
    "NETRA",
    "scam detection",
    "fraud network",
    "digital arrest",
    "public safety",
    "AI intelligence",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} dark h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#09090b] text-gray-100 font-[family-name:var(--font-inter)]">
        <Navbar />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
