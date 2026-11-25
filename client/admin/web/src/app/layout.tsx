import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/core/providers";

export const metadata: Metadata = {
  title: { default: "InaiFlow Platform Console", template: "%s · InaiFlow Console" },
  robots: { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } },
  icons: { icon: "/brand/logo-mark.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
