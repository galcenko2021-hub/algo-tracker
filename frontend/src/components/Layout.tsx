import { NavLink, Outlet } from "react-router-dom";
import { useDue } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import Logo from "./Logo";
import { Button } from "./ui";

const LINKS = [
  { to: "/", label: "Дашборд", end: true },
  { to: "/solves", label: "Решения" },
  { to: "/topics", label: "Темы" },
  { to: "/reviews", label: "Повторения" },
  { to: "/recommendations", label: "Рекомендации" },
  { to: "/settings", label: "Настройки" },
];

function NavItems({ dueCount, compact }: { dueCount: number; compact?: boolean }) {
  return LINKS.map((link) => (
    <NavLink
      key={link.to}
      to={link.to}
      end={link.end}
      className={({ isActive }) =>
        `flex shrink-0 items-center justify-between gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
          compact ? "" : "lg:py-2"
        } ${
          isActive
            ? "bg-surface font-medium text-fg shadow-[inset_0_0_0_1px_var(--line)]"
            : "text-muted hover:bg-surface-2 hover:text-fg"
        }`
      }
    >
      {link.label}
      {link.to === "/reviews" && dueCount > 0 && (
        <span className="rounded bg-accent-soft px-1.5 text-xs font-medium leading-5 text-accent">
          {dueCount}
        </span>
      )}
    </NavLink>
  ));
}

export default function Layout() {
  const { user, logout } = useAuth();
  const due = useDue();
  const dueCount = due.data?.count ?? 0;

  return (
    <div className="min-h-screen lg:flex">
      {/* Desktop: quiet sidebar. */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line px-4 py-6 lg:flex">
        <Logo className="px-3" />
        <nav aria-label="Основная навигация" className="mt-8 flex flex-col gap-0.5">
          <NavItems dueCount={dueCount} />
        </nav>
        <div className="mt-auto border-t border-line px-3 pt-4">
          <p className="truncate text-xs text-muted" title={user?.email}>
            {user?.email}
          </p>
          <Button variant="ghost" className="-ml-3 mt-1" onClick={() => void logout()}>
            Выйти
          </Button>
        </div>
      </aside>

      {/* Mobile and tablet: compact header with a scrollable nav row. */}
      <header className="border-b border-line lg:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <Logo />
          <Button variant="ghost" onClick={() => void logout()}>
            Выйти
          </Button>
        </div>
        <nav
          aria-label="Основная навигация"
          className="flex gap-1 overflow-x-auto px-3 pb-3 [scrollbar-width:none]"
        >
          <NavItems dueCount={dueCount} compact />
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl min-w-0 flex-1 px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
        <Outlet />
      </main>
    </div>
  );
}
