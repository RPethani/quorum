import type { Metadata } from "next";
import { ThemeProvider } from "@/components/design-system/theme-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quorum",
  description: "Where premium AI subscriptions deliberate together.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-canvas text-fg-primary antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
