import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
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
      suppressHydrationWarning
    >
      <body
        className="min-h-full flex flex-col bg-[#09090b] text-gray-100 font-[family-name:var(--font-inter)]"
        suppressHydrationWarning
      >
        <Navbar />
        <main className="flex-1">{children}</main>
        <footer className="w-full border-t border-white/[0.06] bg-[#09090b]">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-center gap-2">
            <span className="text-xs text-gray-500">
              Built By —{" "}
              <span className="text-gray-300 font-medium">
                Bhaskar Ranjan Karn
              </span>{" "}
              for{" "}
              <span className="text-cyan-400 font-semibold">
                ET GEN AI Hackathon
              </span>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
