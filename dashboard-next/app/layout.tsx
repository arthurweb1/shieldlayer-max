// app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ShieldLayer Max",
  description: "Enterprise AI Gateway — EU AI Act Compliant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className} style={{ background: "#0f0f10", color: "#e4e4e7" }}>
        <Sidebar />
        <TopBar />
        <main className="ml-16 pt-14 min-h-screen p-8">{children}</main>
      </body>
    </html>
  );
}
