import { api } from "./client";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    api<{ access_token: string }>("/auth/login", { method: "POST", body: { email, password }, auth: false }),

  register: (email: string, password: string, fullName: string | null) =>
    api<User>("/auth/register", {
      method: "POST",
      body: { email, password, full_name: fullName },
      auth: false,
    }),

  /** Revokes the refresh cookie server-side and clears it. */
  logout: () => api<{ message: string }>("/auth/logout", { method: "POST", auth: false }),

  me: () => api<User>("/auth/me"),
};
