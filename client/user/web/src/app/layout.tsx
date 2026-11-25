import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";

// Inter (variable, latin) self-hosted so builds never depend on fonts.googleapis.com (blocked in CI/sandbox).
const inter = localFont({ src: "./fonts/inter-latin-var.woff2", variable: "--font-inter", display: "swap", weight: "100 900" });

export const metadata: Metadata = {
  title: { default: process.env.NEXT_PUBLIC_APP_NAME ?? "InaiFlow", template: "%s · InaiFlow" },
  description: "Accounts, shop floor and ISO records — in one place.",
  icons: { icon: "/brand/logo-mark.png" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { themeColor: "#F9F9FB", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN" className={inter.variable}>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
