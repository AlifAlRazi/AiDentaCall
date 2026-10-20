"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  isAuthenticated: boolean;
  user: string | null;
  login: (token: string, username: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  user: null,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true); // default true for immediate demo/preview
  const [user, setUser] = useState<string | null>("admin");
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const saved = localStorage.getItem("dentacall_admin_auth");
    if (saved) {
      setIsAuthenticated(true);
      setUser("admin");
    }
  }, []);

  const login = (token: string, username: string) => {
    localStorage.setItem("dentacall_admin_auth", token);
    setIsAuthenticated(true);
    setUser(username);
    router.push("/");
  };

  const logout = () => {
    localStorage.removeItem("dentacall_admin_auth");
    setIsAuthenticated(false);
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
