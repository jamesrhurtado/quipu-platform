import { Configuration, LogLevel } from "@azure/msal-browser";

const clientId = process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || "";
const tenantId = process.env.NEXT_PUBLIC_AZURE_TENANT_ID || "";

export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: typeof window !== "undefined" ? `${window.location.origin}/auth/callback` : "/auth/callback",
    postLogoutRedirectUri: "/",
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
    },
  },
};

export const loginRequest = {
  scopes: ["openid", "profile", "email"],
};

export const isAuthConfigured = Boolean(clientId && tenantId);
