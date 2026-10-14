import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth-context";
import { Loading } from "./ui";

/** Renders child routes only for a signed-in user; everyone else is sent to /login. */
export default function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Loading label="Проверяем вход…" />;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}
