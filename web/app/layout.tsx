import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Literata, Source_Sans_3 } from "next/font/google";

import "./globals.css";

const literata = Literata({
  subsets: ["latin"],
  variable: "--font-display",
});

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "PGD Teletrabalho — Unifesp",
  description:
    "Pergunte sobre as regras vigentes de teletrabalho no instantâneo normativo da Unifesp.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${literata.variable} ${sourceSans.variable}`}>{children}</body>
    </html>
  );
}
