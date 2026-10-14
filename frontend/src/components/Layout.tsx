import { NavLink, Outlet } from "react-router-dom";
import { useDue } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { Button } from "./ui";

const LINKS = [
  { to: "/", label: "Дашборд", end: true },
  { to: "/solves", label: "Решения" },
  { to: "/topics", label: "Темы" },
  { to: "/reviews", label: "Повторения" },
  { to: "/recommendations", label: "Рекомендации" },
  { to: "/settings", label: "Настройки" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const due = useDue();
  const dueCount = due.data?.count ?? 0;

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="font-mono text-base font-semibold text-accent">algo-tracker</span>
          <nav aria-label="Основная навигация" className="flex flex-1 flex-wrap gap-1">
            {LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm transition ${
                    isActive ? "bg-surface-2 text-accent" : "text-muted hover:text-fg"
                  }`
                }
              >
                {link.label}
                {link.to === "/reviews" && dueCount > 0 && (
                  <span className="ml-1.5 rounded-full bg-accent px-1.5 font-mono text-xs text-accent-fg">
                    {dueCount}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-sm text-muted">
            <span className="hidden max-w-[16rem] truncate sm:inline">{user?.email}</span>
            <Button variant="secondary" onClick={() => void logout()}>
              Выйти
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
