"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-provider";

export default function LoginPage() {
  const { isAuthenticated, isLoading, authEnabled, login } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!authEnabled || isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, authEnabled, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-400">
        Loading...
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-950">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-sentinel-500 mb-2">Quipu</h1>
        <p className="text-gray-400">
          AI Early Warning System for Peruvian Municipalities
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 w-full max-w-sm">
        <h2 className="text-lg font-semibold text-gray-100 mb-4 text-center">
          Sign in
        </h2>
        <button
          onClick={login}
          className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
        >
          <svg className="w-5 h-5" viewBox="0 0 23 23" fill="none">
            <path d="M1 1h10v10H1z" fill="#f25022" />
            <path d="M12 1h10v10H12z" fill="#7fba00" />
            <path d="M1 12h10v10H1z" fill="#00a4ef" />
            <path d="M12 12h10v10H12z" fill="#ffb900" />
          </svg>
          Sign in with Microsoft
        </button>
        <p className="mt-4 text-xs text-gray-500 text-center">
          Uses your organization&apos;s Azure Entra ID account
        </p>
      </div>
    </div>
  );
}
