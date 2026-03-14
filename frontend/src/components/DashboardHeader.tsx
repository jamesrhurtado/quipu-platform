"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth-provider";
import Link from "next/link";

interface Props {
  connected: boolean;
  eventCount: number;
}

export default function DashboardHeader({ connected, eventCount }: Props) {
  const { user, orgContext, authEnabled, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold text-sentinel-500">Quipu</h1>
        <span className="text-xs text-gray-400">
          {orgContext?.municipality
            ? `${orgContext.municipality} — Disaster & Climate Risk Monitor`
            : "Disaster & Climate Risk Monitor"}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-green-500 animate-pulse-dot" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-gray-400">
            {connected ? "Live" : "Disconnected"}
          </span>
        </div>
        <span className="text-xs text-gray-500">{eventCount} events</span>

        {authEnabled && user && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-800 transition-colors"
            >
              <div className="w-6 h-6 rounded-full bg-sentinel-600 flex items-center justify-center text-xs font-bold text-white">
                {(user.name || user.username || "U")[0].toUpperCase()}
              </div>
              <span className="text-xs text-gray-300 max-w-[120px] truncate">
                {user.name || user.username}
              </span>
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-xl py-1 z-50">
                <Link
                  href="/dashboard/alerts"
                  className="block px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
                  onClick={() => setMenuOpen(false)}
                >
                  Alert History
                </Link>
                <Link
                  href="/dashboard/settings"
                  className="block px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
                  onClick={() => setMenuOpen(false)}
                >
                  Settings
                </Link>
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    logout();
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
