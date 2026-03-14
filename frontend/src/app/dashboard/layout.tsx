"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-provider";
import { fetchMe, setAuthTokenGetter } from "@/lib/api";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading, authEnabled, getAccessToken, setOrgContext } = useAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  // Wire up auth token getter for API calls
  useEffect(() => {
    if (authEnabled) {
      setAuthTokenGetter(getAccessToken);
    }
  }, [authEnabled, getAccessToken]);

  // Auth guard + onboarding check
  useEffect(() => {
    if (!authEnabled) {
      setChecking(false);
      return;
    }
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/auth/login");
      return;
    }

    // Check if user has completed onboarding
    fetchMe()
      .then((data) => {
        if (!data.organization || !data.organization.onboarding_completed) {
          router.replace("/setup");
        } else {
          setOrgContext(data.organization);
          setChecking(false);
        }
      })
      .catch(() => {
        setChecking(false); // Let it through on error, dashboard will show stale data
      });
  }, [authEnabled, isAuthenticated, isLoading, router, setOrgContext]);

  if ((authEnabled && isLoading) || checking) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-400">
        Loading...
      </div>
    );
  }

  if (authEnabled && !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
