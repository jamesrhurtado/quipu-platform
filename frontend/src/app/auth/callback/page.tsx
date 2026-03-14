"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-provider";

export default function AuthCallbackPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (isAuthenticated) {
      router.replace("/dashboard");
    } else {
      router.replace("/auth/login");
    }
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-400">
      <div className="text-center">
        <div className="animate-spin w-8 h-8 border-2 border-sentinel-500 border-t-transparent rounded-full mx-auto mb-4" />
        <p>Completing sign in...</p>
      </div>
    </div>
  );
}
