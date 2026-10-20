"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Sidebar, TopHeader } from "@/components/Navigation";
import { AuthProvider } from "@/context/AuthContext";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  if (isLoginPage) {
    return <AuthProvider>{children}</AuthProvider>;
  }

  return (
    <AuthProvider>
      <div className="app-container">
        <Sidebar />
        <div className="main-content">
          <TopHeader />
          <main className="content-body">{children}</main>
        </div>
      </div>
    </AuthProvider>
  );
}
