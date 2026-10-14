import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthContext, type AuthContextValue } from "../lib/auth-context";
import { authValue } from "../test-utils";
import ProtectedRoute from "./ProtectedRoute";

function renderAt(auth: AuthContextValue, path = "/secret") {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/secret" element={<p>secret content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("<ProtectedRoute>", () => {
  it("redirects anonymous visitors to /login", () => {
    renderAt(authValue("anonymous"));
    expect(screen.getByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("shows the page to signed-in users", () => {
    renderAt(authValue("authenticated"));
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });

  it("waits while the session is being restored instead of redirecting", () => {
    renderAt(authValue("loading"));
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("login page")).not.toBeInTheDocument();
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });
});
