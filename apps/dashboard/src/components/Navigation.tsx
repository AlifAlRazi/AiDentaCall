"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Phone,
  Calendar,
  PhoneCall,
  Activity,
  ShieldCheck,
  LogOut,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export function Sidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  const navItems = [
    { label: "Overview & Metrics", href: "/", icon: LayoutDashboard },
    { label: "Call Logs", href: "/calls", icon: Phone },
    { label: "Calendar", href: "/calendar", icon: Calendar },
    { label: "Browser Voice Agent", href: "/call", icon: PhoneCall },
  ];

  return (
    <aside className="sidebar">
      {/* Brand & Clinic Info */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "32px", padding: "0 8px" }}>
        <div
          style={{
            width: "40px",
            height: "40px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #0ea5e9, #10b981)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            boxShadow: "0 0 15px rgba(14, 165, 233, 0.4)",
          }}
        >
          <Sparkles size={22} />
        </div>
        <div>
          <h1 style={{ fontSize: "1.05rem", fontWeight: 700, letterSpacing: "-0.02em", color: "#f8fafc" }}>
            DentaCall AI
          </h1>
          <p style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Grand Canal Dental Clinic</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 14px",
                borderRadius: "8px",
                fontSize: "0.9rem",
                fontWeight: isActive ? 600 : 500,
                color: isActive ? "#38bdf8" : "#94a3b8",
                backgroundColor: isActive ? "rgba(14, 165, 233, 0.12)" : "transparent",
                border: isActive ? "1px solid rgba(14, 165, 233, 0.3)" : "1px solid transparent",
                transition: "all 0.15s ease",
              }}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Admin Profile & Status */}
      <div
        style={{
          padding: "14px",
          background: "rgba(255, 255, 255, 0.03)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "10px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: "#1e293b",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#38bdf8",
              }}
            >
              AD
            </div>
            <div>
              <p style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>{user || "Admin"}</p>
              <p style={{ fontSize: "0.7rem", color: "#64748b" }}>Clinic Manager</p>
            </div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            style={{ color: "#64748b", padding: "4px" }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}

export function TopHeader() {
  return (
    <header className="top-header">
      {/* Clinic & Phone Indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div className="pulse-dot" />
          <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--emerald)" }}>
            Live Receptionist Active
          </span>
        </div>
        <span style={{ color: "var(--border-card)" }}>|</span>
        <span style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>
          Twilio Inbound: <strong style={{ color: "#f8fafc" }}>+353 1 234 5678</strong>
        </span>
      </div>

      {/* Right Controls: Today Spend + Call Now CTA */}
      <div style={{ display: "flex", alignItems: "center", gap: "18px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid var(--border-subtle)",
            padding: "6px 14px",
            borderRadius: "var(--radius-pill)",
            fontSize: "0.8rem",
          }}
        >
          <Activity size={15} color="#38bdf8" />
          <span style={{ color: "var(--text-dim)" }}>Today Spend:</span>
          <strong style={{ color: "#f8fafc" }}>$3.14</strong>
          <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>/ $25.00 Cap</span>
        </div>

        <Link href="/call" className="btn-call-now">
          <PhoneCall size={16} />
          <span>Call Now</span>
        </Link>
      </div>
    </header>
  );
}
