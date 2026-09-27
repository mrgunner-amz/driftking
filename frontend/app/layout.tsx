import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DriftKing",
  description: "See what changed in your infrastructure.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas text-fg antialiased">
        {children}
      </body>
    </html>
  );
}
