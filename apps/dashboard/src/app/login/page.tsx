"use client";

import React, { useState } from "react";
import { Sparkles, Lock, User, ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/dashboard/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (data.success && data.token) {
        login(data.token, username);
      } else {
        setError(data.message || "Invalid credentials.");
      }
    } catch {
      // Offline fallback
      if (username.toLowerCase() === "admin" && password === "dentacall2026") {
        login("offline_token_admin", "admin");
      } else {
        setError("Invalid username or password. (Demo: admin / dentacall2026)");
      }
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = () => {
    setUsername("admin");
    setPassword("dentacall2026");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        background: "radial-gradient(ellipse at top, #111e38 0%, #080c14 70%)",
      }}
    >
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: "440px",
          padding: "40px 36px",
          background: "rgba(18, 25, 41, 0.85)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(14, 165, 233, 0.15)",
        }}
      >
        {/* Header Branding */}
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "14px",
              background: "linear-gradient(135deg, #0ea5e9, #10b981)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              marginBottom: "16px",
              boxShadow: "0 0 25px rgba(14, 165, 233, 0.4)",
            }}
          >
            <Sparkles size={28} />
          </div>
          <h2 style={{ fontSize: "1.6rem", fontWeight: 700, letterSpacing: "-0.03em" }}>
            DentaCall Dashboard
          </h2>
          <p style={{ fontSize: "0.88rem", color: "var(--text-dim)", marginTop: "6px" }}>
            Grand Canal Dental Clinic — Practice Portal
          </p>
        </div>

        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "rgba(244, 63, 94, 0.12)",
              border: "1px solid rgba(244, 63, 94, 0.3)",
              borderRadius: "var(--radius-md)",
              color: "#fb7185",
              fontSize: "0.85rem",
              marginBottom: "20px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, color: "var(--text-dim)", marginBottom: "8px" }}>
              Username
            </label>
            <div style={{ position: "relative" }}>
              <User size={16} style={{ position: "absolute", left: "14px", top: "14px", color: "var(--text-muted)" }} />
              <input
                type="text"
                className="input-field"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                style={{ paddingLeft: "40px" }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, color: "var(--text-dim)", marginBottom: "8px" }}>
              Password
            </label>
            <div style={{ position: "relative" }}>
              <Lock size={16} style={{ position: "absolute", left: "14px", top: "14px", color: "var(--text-muted)" }} />
              <input
                type="password"
                className="input-field"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ paddingLeft: "40px" }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center", marginTop: "8px", padding: "12px" }}
          >
            <span>{loading ? "Authenticating..." : "Sign In to Dashboard"}</span>
            <ArrowRight size={16} />
          </button>

          <button
            type="button"
            onClick={fillDemo}
            className="btn-secondary"
            style={{ width: "100%", justifyContent: "center", fontSize: "0.85rem" }}
          >
            <ShieldCheck size={16} />
            <span>Use Demo Admin Credentials</span>
          </button>
        </form>

        <p style={{ textAlign: "center", fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "24px" }}>
          Secure staff portal. All voice telemetry and patient transcripts encrypted.
        </p>
      </div>
    </div>
  );
}
