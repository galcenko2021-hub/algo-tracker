import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import AuthProvider from "./components/AuthProvider";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { createQueryClient } from "./lib/query-client";
import AuthPage from "./pages/AuthPage";
import DashboardPage from "./pages/DashboardPage";
import RecommendationsPage from "./pages/RecommendationsPage";
import ReviewsPage from "./pages/ReviewsPage";
import SettingsPage from "./pages/SettingsPage";
import SolvesPage from "./pages/SolvesPage";
import { Loading } from "./components/ui";

// Recharts is heavy: load the topics page (the only one with charts) on demand.
const TopicsPage = lazy(() => import("./pages/TopicsPage"));

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="solves" element={<SolvesPage />} />
          <Route
            path="topics"
            element={
              <Suspense fallback={<Loading />}>
                <TopicsPage />
              </Suspense>
            }
          />
          <Route path="reviews" element={<ReviewsPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-sm p-10 text-center">
      <p className="font-mono text-2xl">404</p>
      <p className="mt-2 text-muted">Такой страницы нет.</p>
      <a href="/" className="mt-4 inline-block text-accent underline">
        На главную
      </a>
    </div>
  );
}

export default function App() {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
