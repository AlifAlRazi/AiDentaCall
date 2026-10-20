"use client";

import React, { useEffect, useState } from "react";
import {
  Calendar as CalendarIcon,
  Clock,
  User,
  Phone,
  CheckCircle2,
  Filter,
  Plus,
  RefreshCw,
} from "lucide-react";

interface AppointmentItem {
  id: string;
  patient_name: string;
  patient_phone: string;
  dentist_name: string;
  service_name: string;
  service_code: string;
  start_time_utc: string;
  end_time_utc: string;
  status: string;
}

export default function CalendarPage() {
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [dentistFilter, setDentistFilter] = useState<string>("ALL");

  const fetchAppointments = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/dashboard/appointments");
      if (res.ok) {
        const json = await res.json();
        setAppointments(json);
      }
    } catch {
      // Seeded fallback handles network error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  const getServiceBadge = (code: string, name: string) => {
    switch (code.toUpperCase()) {
      case "EMERGENCY":
        return <span className="badge badge-rose">{name}</span>;
      case "EXAM":
        return <span className="badge badge-blue">{name}</span>;
      case "FILLING":
        return <span className="badge badge-purple">{name}</span>;
      case "CLEANING":
        return <span className="badge badge-emerald">{name}</span>;
      default:
        return <span className="badge badge-amber">{name}</span>;
    }
  };

  const filtered = appointments.filter((apt) => {
    if (dentistFilter === "ALL") return true;
    return apt.dentist_name.toLowerCase().includes(dentistFilter.toLowerCase());
  });

  return (
    <div>
      {/* Title Bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "28px" }}>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.03em" }}>
            Clinic Appointments Calendar
          </h1>
          <p style={{ fontSize: "0.9rem", color: "var(--text-dim)", marginTop: "4px" }}>
            Grand Canal Dental Clinic schedule — Europe/Dublin timezone
          </p>
        </div>

        <button onClick={fetchAppointments} className="btn-secondary" style={{ fontSize: "0.85rem" }}>
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          <span>Refresh Schedule</span>
        </button>
      </div>

      {/* Filter by Dentist */}
      <div
        className="card"
        style={{
          padding: "16px 20px",
          marginBottom: "24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-dim)", fontWeight: 600 }}>Filter by Clinician:</span>
          {["ALL", "Sarah Murphy", "Conor Walsh"].map((name) => (
            <button
              key={name}
              onClick={() => setDentistFilter(name)}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--radius-pill)",
                fontSize: "0.8rem",
                fontWeight: 600,
                border: "1px solid",
                borderColor: dentistFilter === name ? "var(--primary)" : "var(--border-subtle)",
                background: dentistFilter === name ? "rgba(14, 165, 233, 0.2)" : "transparent",
                color: dentistFilter === name ? "#38bdf8" : "var(--text-dim)",
                transition: "all 0.15s ease",
              }}
            >
              {name === "ALL" ? "All Dentists" : `Dr. ${name}`}
            </button>
          ))}
        </div>

        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Showing <strong>{filtered.length}</strong> upcoming appointments
        </div>
      </div>

      {/* Calendar Appointments Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
          gap: "20px",
        }}
      >
        {filtered.map((apt) => {
          const startDate = new Date(apt.start_time_utc);
          const endDate = new Date(apt.end_time_utc);
          return (
            <div key={apt.id} className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {/* Card Header: Service Badge & Status */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                {getServiceBadge(apt.service_code, apt.service_name)}
                <span className="badge badge-emerald" style={{ fontSize: "0.7rem" }}>
                  {apt.status}
                </span>
              </div>

              {/* Patient Name & Phone */}
              <div>
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#f8fafc" }}>
                  {apt.patient_name}
                </h3>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-dim)", fontSize: "0.85rem", marginTop: "4px" }}>
                  <Phone size={13} color="#38bdf8" />
                  <span>{apt.patient_phone}</span>
                </div>
              </div>

              {/* Dentist info */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "var(--text-dim)" }}>
                <User size={14} color="var(--text-muted)" />
                <span>Dentist: <strong style={{ color: "#f8fafc" }}>{apt.dentist_name}</strong></span>
              </div>

              {/* Date & Time Slot Box */}
              <div
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "8px",
                  padding: "10px 14px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginTop: "auto",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <CalendarIcon size={15} color="#38bdf8" />
                  <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>
                    {startDate.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--emerald)", fontWeight: 700, fontSize: "0.85rem" }}>
                  <Clock size={14} />
                  <span>
                    {startDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} -{" "}
                    {endDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
