import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "DentaCall — Clinical Voice Receptionist Dashboard",
  description: "Real-time call monitoring, appointments calendar, and latency analytics for Grand Canal Dental Clinic.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
