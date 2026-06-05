import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DhanRadar",
  description: "AI-powered Indian mutual fund & stock radar",
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
