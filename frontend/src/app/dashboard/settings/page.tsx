"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  EmergencyContact,
  OrgSettings,
  addContact,
  deleteContact,
  deleteOrganization,
  fetchContacts,
  fetchSettings,
  testSettingsBluesky,
  testSettingsTeams,
  updateSettingsNotifications,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-provider";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const { orgContext } = useAuth();
  const router = useRouter();
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null);

  // Notification form state
  const [teamsUrl, setTeamsUrl] = useState("");
  const [teamsEnabled, setTeamsEnabled] = useState(false);
  const [bskyHandle, setBskyHandle] = useState("");
  const [bskyPassword, setBskyPassword] = useState("");
  const [bskyEnabled, setBskyEnabled] = useState(false);

  // New contact form
  const [newContact, setNewContact] = useState({ name: "", role: "", phone: "", email: "", notify_on_level: ["critical"] as string[] });
  const [showAddContact, setShowAddContact] = useState(false);

  // Danger zone
  const [confirmDelete, setConfirmDelete] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([fetchSettings(), fetchContacts()]);
      setSettings(s);
      setContacts(c.contacts);
      setTeamsUrl(s.notifications.teams_webhook_url || "");
      setTeamsEnabled(s.notifications.teams_enabled);
      setBskyHandle(s.notifications.bluesky_handle || "");
      setBskyEnabled(s.notifications.bluesky_enabled);
    } catch {
      setMessage({ type: "error", text: "Failed to load settings" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const flash = (type: "ok" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 4000);
  };

  const handleSaveNotifications = async () => {
    setSaving(true);
    try {
      await updateSettingsNotifications({
        teams_webhook_url: teamsUrl || null,
        teams_enabled: teamsEnabled,
        bluesky_handle: bskyHandle || null,
        bluesky_app_password: bskyPassword || undefined,
        bluesky_enabled: bskyEnabled,
      });
      setBskyPassword("");
      flash("ok", "Notification settings saved");
    } catch {
      flash("error", "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleAddContact = async () => {
    if (!newContact.name.trim()) return;
    try {
      await addContact(newContact);
      setNewContact({ name: "", role: "", phone: "", email: "", notify_on_level: ["critical"] });
      setShowAddContact(false);
      const c = await fetchContacts();
      setContacts(c.contacts);
      flash("ok", "Contact added");
    } catch {
      flash("error", "Failed to add contact");
    }
  };

  const handleDeleteContact = async (id: string) => {
    try {
      await deleteContact(id);
      setContacts((prev) => prev.filter((c) => c.id !== id));
      flash("ok", "Contact removed");
    } catch {
      flash("error", "Failed to remove contact");
    }
  };

  const handleDeleteOrg = async () => {
    try {
      await deleteOrganization();
      router.replace("/");
    } catch {
      flash("error", "Failed to delete organization");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-400">
        Loading settings...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-gray-400 hover:text-gray-200 text-sm">
            &larr; Dashboard
          </Link>
          <h1 className="text-lg font-bold text-gray-100">Settings</h1>
        </div>
        {orgContext && (
          <span className="text-sm text-gray-400">{orgContext.municipality}</span>
        )}
      </header>

      <div className="max-w-3xl mx-auto p-6 space-y-8">
        {message && (
          <div
            className={`px-4 py-2 rounded-lg text-sm ${
              message.type === "ok"
                ? "bg-green-900/50 border border-green-700 text-green-200"
                : "bg-red-900/50 border border-red-700 text-red-200"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Municipality Info */}
        {settings && (
          <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Municipality</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Name</span>
                <p className="text-gray-200">{settings.organization.municipality}</p>
              </div>
              <div>
                <span className="text-gray-500">Department</span>
                <p className="text-gray-200">{settings.organization.department || "—"}</p>
              </div>
              <div>
                <span className="text-gray-500">Slug</span>
                <p className="text-gray-200">{settings.organization.slug}</p>
              </div>
              <div>
                <span className="text-gray-500">Created</span>
                <p className="text-gray-200">{new Date(settings.organization.created_at).toLocaleDateString()}</p>
              </div>
            </div>
            {settings.monitored_zones.length > 0 && (
              <div className="mt-4">
                <span className="text-gray-500 text-sm">Monitored Zones</span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {settings.monitored_zones.map((z) => (
                    <span
                      key={z.id}
                      className={`px-2 py-1 rounded-full text-xs border ${
                        z.is_primary
                          ? "bg-sentinel-600/20 border-sentinel-500 text-sentinel-300"
                          : "bg-gray-800 border-gray-700 text-gray-400"
                      }`}
                    >
                      {z.name}{z.is_primary ? " (primary)" : ""}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Notifications */}
        <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-100 mb-4">Notifications</h2>

          {/* Teams */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <label className="text-gray-300 font-medium text-sm">Microsoft Teams</label>
              <button
                onClick={() => setTeamsEnabled(!teamsEnabled)}
                className={`w-10 h-5 rounded-full transition-colors ${teamsEnabled ? "bg-sentinel-600" : "bg-gray-700"}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition-transform mx-0.5 ${teamsEnabled ? "translate-x-5" : ""}`} />
              </button>
            </div>
            {teamsEnabled && (
              <div className="space-y-2">
                <input
                  type="url"
                  value={teamsUrl}
                  onChange={(e) => setTeamsUrl(e.target.value)}
                  placeholder="Teams Incoming Webhook URL"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500 text-sm"
                />
                {teamsUrl && (
                  <button
                    onClick={async () => {
                      try {
                        await testSettingsTeams();
                        flash("ok", "Test card sent to Teams!");
                      } catch {
                        flash("error", "Teams test failed");
                      }
                    }}
                    className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
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
              <label className="text-gray-300 font-medium text-sm">Bluesky</label>
              <button
                onClick={() => setBskyEnabled(!bskyEnabled)}
                className={`w-10 h-5 rounded-full transition-colors ${bskyEnabled ? "bg-sentinel-600" : "bg-gray-700"}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition-transform mx-0.5 ${bskyEnabled ? "translate-x-5" : ""}`} />
              </button>
            </div>
            {bskyEnabled && (
              <div className="space-y-2">
                <input
                  type="text"
                  value={bskyHandle}
                  onChange={(e) => setBskyHandle(e.target.value)}
                  placeholder="handle.bsky.social"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500 text-sm"
                />
                <input
                  type="password"
                  value={bskyPassword}
                  onChange={(e) => setBskyPassword(e.target.value)}
                  placeholder="App password (leave blank to keep current)"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-sentinel-500 text-sm"
                />
                {bskyHandle && (
                  <button
                    onClick={async () => {
                      try {
                        await testSettingsBluesky();
                        flash("ok", "Bluesky credentials verified!");
                      } catch {
                        flash("error", "Bluesky verification failed");
                      }
                    }}
                    className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
                  >
                    Verify
                  </button>
                )}
              </div>
            )}
          </div>

          <button
            onClick={handleSaveNotifications}
            disabled={saving}
            className="px-4 py-2 bg-sentinel-600 hover:bg-sentinel-700 disabled:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? "Saving..." : "Save Notifications"}
          </button>
        </section>

        {/* Emergency Contacts */}
        <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-100">Emergency Contacts</h2>
            <button
              onClick={() => setShowAddContact(!showAddContact)}
              className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
            >
              {showAddContact ? "Cancel" : "+ Add"}
            </button>
          </div>

          {showAddContact && (
            <div className="bg-gray-800 rounded-lg p-4 mb-4">
              <div className="grid grid-cols-2 gap-2 mb-2">
                <input
                  type="text"
                  value={newContact.name}
                  onChange={(e) => setNewContact({ ...newContact, name: e.target.value })}
                  placeholder="Name"
                  className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                />
                <input
                  type="text"
                  value={newContact.role}
                  onChange={(e) => setNewContact({ ...newContact, role: e.target.value })}
                  placeholder="Role"
                  className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                />
                <input
                  type="tel"
                  value={newContact.phone}
                  onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })}
                  placeholder="Phone"
                  className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                />
                <input
                  type="email"
                  value={newContact.email}
                  onChange={(e) => setNewContact({ ...newContact, email: e.target.value })}
                  placeholder="Email"
                  className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-sentinel-500"
                />
              </div>
              <div className="flex gap-2 mb-3">
                {["elevated", "high", "critical"].map((level) => (
                  <button
                    key={level}
                    onClick={() => {
                      const levels = newContact.notify_on_level.includes(level)
                        ? newContact.notify_on_level.filter((l) => l !== level)
                        : [...newContact.notify_on_level, level];
                      setNewContact({ ...newContact, notify_on_level: levels });
                    }}
                    className={`px-2 py-1 rounded text-xs border transition-colors ${
                      newContact.notify_on_level.includes(level)
                        ? level === "critical" ? "bg-red-900/30 border-red-600 text-red-300"
                          : level === "high" ? "bg-orange-900/30 border-orange-600 text-orange-300"
                          : "bg-yellow-900/30 border-yellow-600 text-yellow-300"
                        : "bg-gray-900 border-gray-700 text-gray-500"
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
              <button
                onClick={handleAddContact}
                className="px-4 py-1.5 bg-sentinel-600 hover:bg-sentinel-700 text-white rounded text-sm transition-colors"
              >
                Add Contact
              </button>
            </div>
          )}

          {contacts.length === 0 ? (
            <p className="text-gray-500 text-sm">No emergency contacts configured.</p>
          ) : (
            <div className="space-y-2">
              {contacts.map((c) => (
                <div key={c.id} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
                  <div>
                    <p className="text-gray-200 text-sm font-medium">{c.name}</p>
                    <p className="text-gray-500 text-xs">
                      {[c.role, c.email, c.phone].filter(Boolean).join(" | ")}
                    </p>
                    <div className="flex gap-1 mt-1">
                      {c.notify_on_level.map((l) => (
                        <span
                          key={l}
                          className={`px-1.5 py-0.5 rounded text-[10px] ${
                            l === "critical" ? "bg-red-900/30 text-red-400"
                              : l === "high" ? "bg-orange-900/30 text-orange-400"
                              : "bg-yellow-900/30 text-yellow-400"
                          }`}
                        >
                          {l}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteContact(c.id)}
                    className="text-red-400 hover:text-red-300 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Danger Zone */}
        <section className="bg-gray-900 border border-red-900/50 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-red-400 mb-2">Danger Zone</h2>
          <p className="text-gray-400 text-sm mb-4">
            Deleting your organization will remove all monitoring configuration. This cannot be undone.
          </p>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="px-4 py-2 bg-red-900/50 hover:bg-red-900 text-red-300 border border-red-800 rounded-lg text-sm transition-colors"
            >
              Delete Organization
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <button
                onClick={handleDeleteOrg}
                className="px-4 py-2 bg-red-700 hover:bg-red-600 text-white rounded-lg text-sm transition-colors"
              >
                Confirm Delete
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
