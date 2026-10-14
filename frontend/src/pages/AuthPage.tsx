import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { Button, Card, ErrorMessage, Field } from "../components/ui";
import { useAuth } from "../lib/auth-context";
import { inputClass } from "../lib/styles";
import { validateCredentials } from "../lib/validation";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const isRegister = mode === "register";
  const { status, login, register } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to={from} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateCredentials(email, password, isRegister);
    setErrors(found);
    setSubmitError(null);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    try {
      await (isRegister ? register(email.trim(), password) : login(email.trim(), password));
    } catch (error) {
      setSubmitError(error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="mb-1 font-mono text-2xl font-semibold text-accent">algo-tracker</h1>
      <p className="mb-6 text-sm text-muted">
        Трекер решённых задач: теплокарта, разбор по темам и напоминания о повторении.
      </p>
      <Card>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <h2 className="font-mono text-lg">{isRegister ? "Регистрация" : "Вход"}</h2>
          <Field label="Email" htmlFor="email" error={errors.email}>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field
            label={isRegister ? "Пароль (минимум 8 символов)" : "Пароль"}
            htmlFor="password"
            error={errors.password}
          >
            <input
              id="password"
              type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {submitError !== null && <ErrorMessage error={submitError} />}
          <Button type="submit" disabled={busy}>
            {busy ? "Подождите…" : isRegister ? "Создать аккаунт" : "Войти"}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm text-muted">
        {isRegister ? (
          <>
            Уже есть аккаунт?{" "}
            <Link className="text-accent underline" to="/login">
              Войти
            </Link>
          </>
        ) : (
          <>
            Нет аккаунта?{" "}
            <Link className="text-accent underline" to="/register">
              Зарегистрироваться
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
