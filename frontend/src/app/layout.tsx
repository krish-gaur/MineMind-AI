import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";
import { DatasetProvider } from "@/lib/dataset-context";

export const metadata: Metadata = {
  title: {
    default: "MineMind AI",
    template: "%s | MineMind AI",
  },
  description:
    "Manganese exploration and production intelligence for SIH26009. Synthetic demonstration data is labelled throughout.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#10291f",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <DatasetProvider>
          <AppShell>{children}</AppShell>
        </DatasetProvider>
      </body>
    </html>
  );
}
