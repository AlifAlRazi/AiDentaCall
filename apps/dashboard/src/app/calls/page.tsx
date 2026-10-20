"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Phone,
  Search,
  Filter,
  ArrowRight,
  RefreshCw,
  Clock,
  DollarSign,
  AlertCircle,
} from "lucide-react";

interface CallItem {
  id: string;
  call_sid: string | null;
  caller_phone: string | null;
  status: string;
  outcome: string;
  duration_seconds: number;
  estimated_cost_usd: number;
  summary: string | null;
  created_at_utc: string;
}

export default function CallsListPage() {
  const [calls, setCalls] = useState<CallItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>("");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const fetchCalls = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (outcomeFilter !== "ALL") params.set("outcome", outcomeFilter);
      if (statusFilter !== "ALL") params.set("status", statusFilter);
      if (search.trim()) params.set("search", search.trim());

      const url = `/api/dashboard/calls?${params.toString()}`;
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setCalls(json);
      }
    } catch {
      // Seeded fallback handles network error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, [outcomeFilter, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCalls();
  };

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome.toUpperCase()) {
      case "BOOKED":
      case "CONFIRMED":
        return <span className="badge badge-emerald">Booked</span>;
      case "DROPPED":
        return <span className="badge badge-rose">Dropped</span>;
      case "INQUIRY":
        return <span className="badge badge-blue">Inquiry</span>;
      case "RESCHEDULED":
        return <span className="badge badge-purple">Rescheduled</span>;
      default:
        return <span className="badge badge-amber">{outcome}</span>;
    }
  };

  return (
    <div>
      {/* Title */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "28px" }}>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.03em" }}>
            Patient Call Log Explorer
          </h1>
          <p style={{ fontSize: "0.9rem", color: "var(--text-dim)", marginTop: "4px" }}>
            Complete audit trail of inbound voice calls, transcripts, tool calls, and costs
          </p>
        </div>

        <button onClick={fetchCalls} className="btn-secondary" style={{ fontSize: "0.85rem" }}>
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          <span>Refresh List</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="card"
        style={{
          padding: "18px 24px",
          marginBottom: "24px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
        }}
      >
        {/* Search */}
        <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: "8px", flex: 1, minWidth: "260px" }}>
          <div style={{ position: "relative", width: "100%" }}>
            <Search size={16} style={{ position: "absolute", left: "14px", top: "12px", color: "var(--text-muted)" }} />
            <input
              type="text"
              className="input-field"
              placeholder="Search by phone number (+353...) or summary..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: "38px" }}
            />
          </div>
          <button type="submit" className="btn-secondary" style={{ padding: "0 18px" }}>
            Search
          </button>
        </form>

        {/* Outcome Filter Pills */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginRight: "4px" }}>Outcome:</span>
          {["ALL", "BOOKED", "INQUIRY", "RESCHEDULED", "DROPPED"].map((opt) => (
            <button
              key={opt}
              onClick={() => setOutcomeFilter(opt)}
              style={{
                padding: "6px 12px",
                borderRadius: "var(--radius-pill)",
                fontSize: "0.78rem",
                fontWeight: 600,
                border: "1px solid",
                borderColor: outcomeFilter === opt ? "var(--primary)" : "var(--border-subtle)",
                background: outcomeFilter === opt ? "rgba(14, 165, 233, 0.2)" : "transparent",
                color: outcomeFilter === opt ? "#38bdf8" : "var(--text-dim)",
                transition: "all 0.15s ease",
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {/* Calls Table */}
      <div className="card">
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Caller Phone</th>
                <th>Call SID</th>
                <th>Outcome</th>
                <th>Duration</th>
                <th>Cost</th>
                <th>Clinical Summary</th>
                <th>Timestamp</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {calls.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "48px 24px", color: "var(--text-dim)" }}>
                    No calls matched the selected filters.
                  </td>
                </tr>
              ) : (
                calls.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Phone size={14} color="#38bdf8" />
                        <strong style={{ color: "#f8fafc" }}>{c.caller_phone || "Web Caller"}</strong>
                      </div>
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {c.call_sid || "LIVEKIT-WEB"}
                    </td>
                    <td>{getOutcomeBadge(c.outcome)}</td>
                    <td>{Math.round(c.duration_seconds)}s</td>
                    <td style={{ fontWeight: 600, color: "#38bdf8" }}>
                      ${c.estimated_cost_usd.toFixed(4)}
                    </td>
                    <td style={{ maxWidth: "320px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c.summary || "Call processed"}
                    </td>
                    <td style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      {new Date(c.created_at_utc).toLocaleString()}
                    </td>
                    <td>
                      <Link
                        href={`/calls/${c.id}`}
                        className="btn-secondary"
                        style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                      >
                        <span>Detail</span>
                        <ArrowRight size={13} />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
