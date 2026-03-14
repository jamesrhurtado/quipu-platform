"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Municipality,
  completeOnboarding,
  createOrganization,
  fetchMunicipalities,
  fetchNearbyMunicipalities,
  testBluesky,
  testTeams,
  updateContacts,
  updateNotifications,
} from "@/lib/api";

interface Props {
  onComplete: () => void;
}

export default function OnboardingWizard({ onComplete }: Props) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 state
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Municipality[]>([]);
  const [selected, setSelected] = useState<Municipality | null>(null);
  const [nearby, setNearby] = useState<Municipality[]>([]);
  const [selectedZones, setSelectedZones] = useState<Set<string>>(new Set());

  // Step 2 state
  const [teamsUrl, setTeamsUrl] = useState("");
  const [teamsEnabled, setTeamsEnabled] = useState(false);
  const [bskyHandle, setBskyHandle] = useState("");
  const [bskyPassword, setBskyPassword] = useState("");
  const [bskyEnabled, setBskyEnabled] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  // Step 3 state
  const [contacts, setContacts] = useState<
    { name: string; role: string; phone: string; email: string; notify_on_level: string[] }[]
  >([]);

  // Search municipalities
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const data = await fetchMunicipalities(query);
        setResults(data.municipalities);
      } catch {}
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  // Load nearby when a municipality is selected
  const handleSelect = useCallback(async (m: Municipality) => {
    setSelected(m);
    setQuery(m.name);
    setResults([]);
    try {
      const data = await fetchNearbyMunicipalities(m.name);
      setNearby(data.nearby);
    } catch {}
  }, []);

  const toggleZone = (name: string) => {
    setSelectedZones((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // Step 1 submit
  const handleStep1 = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      await createOrganization(selected.name, Array.from(selectedZones));
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create organization");
    } finally {
      setLoading(false);
    }
  };

  // Step 2 submit
  const handleStep2 = async () => {
    setLoading(true);
    setError(null);
    try {
      await updateNotifications({
        teams_webhook_url: teamsUrl || undefined,
        teams_enabled: teamsEnabled,
        bluesky_handle: bskyHandle || undefined,
        bluesky_app_password: bskyPassword || undefined,
        bluesky_enabled: bskyEnabled,
      });
      setStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save notifications");
    } finally {
      setLoading(false);
    }
  };

  // Step 3 submit
  const handleStep3 = async () => {
    setLoading(true);
    setError(null);
    try {
      if (contacts.length > 0) {
        await updateContacts(contacts);
      }
      await completeOnboarding();
      onComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to complete setup");
    } finally {
      setLoading(false);
    }
  };

  const addContact = () => {
    setContacts((prev) => [...prev, { name: "", role: "", phone: "", email: "", notify_on_level: ["critical"] }]);
  };

  const removeContact = (idx: number) => {
    setContacts((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateContact = (idx: number, field: string, value: string | string[]) => {
    setContacts((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c))
    );
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-sentinel-500 mb-2">Quipu Setup</h1>
          <p className="text-gray-400">Configure your municipality monitoring</p>
          {/* Progress */}
          <div className="flex items-center justify-center gap-2 mt-4">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    s <= step ? "bg-sentinel-600 text-white" : "bg-gray-800 text-gray-500"
                  }`}
                >
                  {s}
                </div>
                {s < 3 && <div className={`w-12 h-0.5 ${s < step ? "bg-sentinel-600" : "bg-gray-800"}`} />}
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-2 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          {/* Step 1: Municipality Selection */}
          {step === 1 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Select Your Municipality</h2>
              <div className="relative">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    if (selected && e.target.value !== selected.name) setSelected(null);
                  }}
                  placeholder="Search for your city (e.g., Cusco, Piura, Lima...)"
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500"
                />
                {results.length > 0 && !selected && (
                  <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-60 overflow-y-auto">
                    {results.map((m) => (
                      <button
                        key={`${m.name}-${m.department}`}
                        onClick={() => handleSelect(m)}
                        className="w-full text-left px-4 py-3 hover:bg-gray-700 border-b border-gray-700 last:border-0"
                      >
                        <span className="text-gray-100 font-medium">{m.name}</span>
                        <span className="text-gray-400 text-sm ml-2">({m.department})</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {selected && (
                <div className="mt-4">
                  <div className="bg-gray-800 rounded-lg p-4 mb-4">
                    <p className="text-gray-300">
                      <span className="font-semibold text-sentinel-400">{selected.name}</span>, {selected.department}
                    </p>
                    <p className="text-gray-500 text-sm mt-1">
                      Coordinates: {selected.lat.toFixed(4)}, {selected.lon.toFixed(4)}
                    </p>
                  </div>

                  {nearby.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-2">
                        Nearby cities to also monitor (within 100km):
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {nearby.map((n) => (
                          <button
                            key={n.name}
                            onClick={() => toggleZone(n.name)}
                            className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                              selectedZones.has(n.name)
                                ? "bg-sentinel-600/20 border-sentinel-500 text-sentinel-300"
                                : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
                            }`}
                          >
                            {n.name}
                            <span className="text-xs ml-1 opacity-60">({n.distance_km}km)</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={handleStep1}
                disabled={!selected || loading}
                className="mt-6 w-full py-3 bg-sentinel-600 hover:bg-sentinel-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium transition-colors"
              >
                {loading ? "Creating..." : "Continue"}
              </button>
            </div>
          )}

          {/* Step 2: Notification Configuration */}
          {step === 2 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Notification Channels</h2>
              <p className="text-gray-400 text-sm mb-6">Configure how you want to receive alerts. You can skip this and set it up later.</p>

              {/* Teams */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-gray-300 font-medium">Microsoft Teams</label>
                  <button
                    onClick={() => setTeamsEnabled(!teamsEnabled)}
                    className={`w-10 h-5 rounded-full transition-colors ${
                      teamsEnabled ? "bg-sentinel-600" : "bg-gray-700"
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full bg-white transition-transform mx-0.5 ${
                        teamsEnabled ? "translate-x-5" : ""
                      }`}
                    />
                  </button>
                </div>
                {teamsEnabled && (
                  <div>
                    <input
                      type="url"
                      value={teamsUrl}
                      onChange={(e) => setTeamsUrl(e.target.value)}
                      placeholder="Teams Incoming Webhook URL"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500 text-sm"
                    />
                    {teamsUrl && (
                      <button
                        onClick={async () => {
                          setTestResult(null);
                          try {
                            // Save first, then test
                            await updateNotifications({
                              teams_webhook_url: teamsUrl,
                              teams_enabled: true,
                              bluesky_enabled: false,
                            });
                            await testTeams();
                            setTestResult("Teams test sent!");
                          } catch {
                            setTestResult("Teams test failed");
                          }
                        }}
                        className="mt-2 px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
                      >
                        Test Connection
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Bluesky */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-gray-300 font-medium">Bluesky</label>
                  <button
                    onClick={() => setBskyEnabled(!bskyEnabled)}
                    className={`w-10 h-5 rounded-full transition-colors ${
                      bskyEnabled ? "bg-sentinel-600" : "bg-gray-700"
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full bg-white transition-transform mx-0.5 ${
                        bskyEnabled ? "translate-x-5" : ""
                      }`}
                    />
                  </button>
                </div>
                {bskyEnabled && (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={bskyHandle}
                      onChange={(e) => setBskyHandle(e.target.value)}
                      placeholder="Bluesky handle (e.g., yourname.bsky.social)"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500 text-sm"
                    />
                    <input
                      type="password"
                      value={bskyPassword}
                      onChange={(e) => setBskyPassword(e.target.value)}
                      placeholder="App password"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500 text-sm"
                    />
                  </div>
                )}
              </div>

              {testResult && (
                <p className="text-sm text-gray-400 mb-4">{testResult}</p>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => setStep(3)}
                  className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg font-medium transition-colors"
                >
                  Skip
                </button>
                <button
                  onClick={handleStep2}
                  disabled={loading}
                  className="flex-1 py-3 bg-sentinel-600 hover:bg-sentinel-700 disabled:bg-gray-700 text-white rounded-lg font-medium transition-colors"
                >
                  {loading ? "Saving..." : "Continue"}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Emergency Contacts */}
          {step === 3 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Emergency Contacts</h2>
              <p className="text-gray-400 text-sm mb-6">Add people who should be notified during emergencies. You can skip this and add them later.</p>

              {contacts.map((c, idx) => (
                <div key={idx} className="bg-gray-800 rounded-lg p-4 mb-3">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-gray-400">Contact {idx + 1}</span>
                    <button
                      onClick={() => removeContact(idx)}
                      className="text-red-400 hover:text-red-300 text-xs"
                    >
                      Remove
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={c.name}
                      onChange={(e) => updateContact(idx, "name", e.target.value)}
                      placeholder="Name"
                      className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                    />
                    <input
                      type="text"
                      value={c.role}
                      onChange={(e) => updateContact(idx, "role", e.target.value)}
                      placeholder="Role"
                      className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                    />
                    <input
                      type="tel"
                      value={c.phone}
                      onChange={(e) => updateContact(idx, "phone", e.target.value)}
                      placeholder="Phone"
                      className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                    />
                    <input
                      type="email"
                      value={c.email}
                      onChange={(e) => updateContact(idx, "email", e.target.value)}
                      placeholder="Email"
                      className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                    />
                  </div>
                  <div className="mt-2 flex gap-2">
                    {["elevated", "high", "critical"].map((level) => (
                      <button
                        key={level}
                        onClick={() => {
                          const levels = c.notify_on_level.includes(level)
                            ? c.notify_on_level.filter((l) => l !== level)
                            : [...c.notify_on_level, level];
                          updateContact(idx, "notify_on_level", levels);
                        }}
                        className={`px-2 py-1 rounded text-xs border transition-colors ${
                          c.notify_on_level.includes(level)
                            ? level === "critical"
                              ? "bg-red-900/30 border-red-600 text-red-300"
                              : level === "high"
                                ? "bg-orange-900/30 border-orange-600 text-orange-300"
                                : "bg-yellow-900/30 border-yellow-600 text-yellow-300"
                            : "bg-gray-900 border-gray-700 text-gray-500"
                        }`}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              <button
                onClick={addContact}
                className="w-full py-2 border border-dashed border-gray-700 text-gray-400 rounded-lg hover:border-gray-600 hover:text-gray-300 transition-colors text-sm mb-4"
              >
                + Add Contact
              </button>

              <div className="flex gap-3">
                <button
                  onClick={handleStep3}
                  disabled={loading}
                  className={`flex-1 py-3 rounded-lg font-medium transition-colors ${
                    contacts.length === 0
                      ? "bg-gray-700 hover:bg-gray-600 text-gray-300"
                      : "bg-sentinel-600 hover:bg-sentinel-700 text-white"
                  }`}
                >
                  {loading ? "Completing..." : contacts.length === 0 ? "Skip & Finish" : "Finish Setup"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
