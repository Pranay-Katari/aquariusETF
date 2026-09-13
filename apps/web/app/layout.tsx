import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Aquarius | Portfolio Studio",
  description: "Build, research and backtest your own thematic portfolios.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
