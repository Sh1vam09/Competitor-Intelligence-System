import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Competitor Intelligence Engine",
  description: "Competitor discovery, brand analysis, and PDF intelligence reports.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
