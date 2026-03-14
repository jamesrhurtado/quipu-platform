"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  AccountInfo,
  EventType,
  PublicClientApplication,
} from "@azure/msal-browser";
import { MsalProvider, useMsal } from "@azure/msal-react";
import { isAuthConfigured, loginRequest, msalConfig } from "./auth-config";

// MSAL instance (singleton)
let msalInstance: PublicClientApplication | null = null;

function getMsalInstance(): PublicClientApplication | null {
  if (!isAuthConfigured) return null;
  if (!msalInstance) {
    msalInstance = new PublicClientApplication(msalConfig);
  }
  return msalInstance;
}

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AccountInfo | null;
  orgContext: OrgContext | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
  setOrgContext: (org: OrgContext | null) => void;
  authEnabled: boolean;
}

export interface OrgContext {
  id: string;
  name: string;
  slug: string;
  municipality: string;
  department: string | null;
  map_center_lat: number;
  map_center_lon: number;
  map_zoom: number;
  onboarding_completed: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  orgContext: null,
  login: async () => {},
  logout: async () => {},
  getAccessToken: async () => null,
  setOrgContext: () => {},
  authEnabled: false,
});

export const useAuth = () => useContext(AuthContext);

function AuthProviderInner({ children }: { children: React.ReactNode }) {
  const { instance, accounts } = useMsal();
  const [isLoading, setIsLoading] = useState(true);
  const [orgContext, setOrgContext] = useState<OrgContext | null>(null);

  const account = accounts[0] || null;
  const isAuthenticated = Boolean(account);

  useEffect(() => {
    // Handle redirect promise on mount
    instance
      .handleRedirectPromise()
      .then((response) => {
        if (response?.account) {
          instance.setActiveAccount(response.account);
        }
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));

    // Set active account if available
    if (account) {
      instance.setActiveAccount(account);
    }
  }, [instance, account]);

  const login = useCallback(async () => {
    try {
      await instance.loginRedirect(loginRequest);
    } catch (err) {
      console.error("Login failed:", err);
    }
  }, [instance]);

  const logout = useCallback(async () => {
    try {
      setOrgContext(null);
      await instance.logoutRedirect({ postLogoutRedirectUri: "/" });
    } catch (err) {
      console.error("Logout failed:", err);
    }
  }, [instance]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!account) return null;
    try {
      const response = await instance.acquireTokenSilent({
        ...loginRequest,
        account,
      });
      return response.idToken;
    } catch {
      // Fallback to interactive
      try {
        const response = await instance.acquireTokenRedirect(loginRequest);
        return null; // Will redirect
      } catch {
        return null;
      }
    }
  }, [instance, account]);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user: account,
        orgContext,
        login,
        logout,
        getAccessToken,
        setOrgContext,
        authEnabled: true,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/** Fallback provider when auth is not configured (MULTI_TENANT_ENABLED=false) */
function NoAuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: true,
        isLoading: false,
        user: null,
        orgContext: null,
        login: async () => {},
        logout: async () => {},
        getAccessToken: async () => null,
        setOrgContext: () => {},
        authEnabled: false,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const instance = getMsalInstance();

  if (!instance) {
    // Auth not configured — pass through without auth
    return <NoAuthProvider>{children}</NoAuthProvider>;
  }

  return (
    <MsalProvider instance={instance}>
      <AuthProviderInner>{children}</AuthProviderInner>
    </MsalProvider>
  );
}
