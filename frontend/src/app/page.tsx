"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-provider";
import Link from "next/link";

export default function LandingPage() {
  const { isAuthenticated, isLoading, authEnabled } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!authEnabled) {
      // No auth configured — go straight to dashboard
      router.replace("/dashboard");
    }
  }, [isLoading, authEnabled, router]);

  // If not auth-enabled, show nothing (redirecting)
  if (!authEnabled || isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-400">
        Loading...
      </div>
    );
  }

  // Auth enabled — show landing page
  return (
    <div className="min-h-screen bg-gray-950">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-4 border-b border-gray-800/50">
        <span className="text-xl font-bold text-sentinel-500">Quipu</span>
        <div className="flex items-center gap-4">
          {isAuthenticated ? (
            <Link
              href="/dashboard"
              className="px-4 py-2 bg-sentinel-600 hover:bg-sentinel-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Go to Dashboard
            </Link>
          ) : (
            <Link
              href="/auth/login"
              className="px-4 py-2 bg-sentinel-600 hover:bg-sentinel-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Sign In
            </Link>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-8 py-24 text-center">
        <h1 className="text-5xl font-bold text-gray-100 mb-6 leading-tight">
          AI Early Warning for
          <br />
          <span className="text-sentinel-500">Your Municipality</span>
        </h1>
        <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
          Quipu monitors earthquakes, wildfires, floods, and climate risks around your city
          in real time using 7 specialized AI agents. Get instant alerts on Teams and Bluesky.
        </p>
        <Link
          href={isAuthenticated ? "/dashboard" : "/auth/login"}
          className="inline-block px-8 py-4 bg-sentinel-600 hover:bg-sentinel-700 text-white rounded-xl text-lg font-semibold transition-colors"
        >
          {isAuthenticated ? "Open Dashboard" : "Get Started"}
        </Link>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-3xl mb-4">📡</div>
            <h3 className="text-lg font-semibold text-gray-100 mb-2">Real-Time Monitoring</h3>
            <p className="text-gray-400 text-sm">
              Continuous data from USGS, GDACS, NASA EONET, NASA FIRMS, and Open-Meteo.
              Events appear on your dashboard within minutes.
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-3xl mb-4">🤖</div>
            <h3 className="text-lg font-semibold text-gray-100 mb-2">Multi-Agent AI</h3>
            <p className="text-gray-400 text-sm">
              7 specialized agents analyze earthquakes, fires, weather anomalies, news, and social media
              to compute risk scores for your area.
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-3xl mb-4">🔔</div>
            <h3 className="text-lg font-semibold text-gray-100 mb-2">Instant Alerts</h3>
            <p className="text-gray-400 text-sm">
              Automatic alerts to Microsoft Teams and Bluesky when risk thresholds are crossed.
              Configure emergency contacts for escalation.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-4xl mx-auto px-8 py-16">
        <h2 className="text-2xl font-bold text-gray-100 text-center mb-12">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-sentinel-600/20 border border-sentinel-600 text-sentinel-400 flex items-center justify-center text-lg font-bold mx-auto mb-4">1</div>
            <h3 className="text-gray-100 font-medium mb-1">Register</h3>
            <p className="text-gray-400 text-sm">Sign in with your Microsoft account and select your municipality.</p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-sentinel-600/20 border border-sentinel-600 text-sentinel-400 flex items-center justify-center text-lg font-bold mx-auto mb-4">2</div>
            <h3 className="text-gray-100 font-medium mb-1">Configure</h3>
            <p className="text-gray-400 text-sm">Set up Teams webhooks, Bluesky, and emergency contacts.</p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-sentinel-600/20 border border-sentinel-600 text-sentinel-400 flex items-center justify-center text-lg font-bold mx-auto mb-4">3</div>
            <h3 className="text-gray-100 font-medium mb-1">Monitor</h3>
            <p className="text-gray-400 text-sm">Your AI-powered dashboard tracks risks 24/7 and alerts you automatically.</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800/50 py-8 text-center text-gray-500 text-sm">
        Quipu — Named after the Inca knotted-string recording system.
        <br />
        Built for Microsoft AI Agents Hackathon.
      </footer>
    </div>
  );
}
