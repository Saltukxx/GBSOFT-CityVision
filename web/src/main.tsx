import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "./i18n";
import "./styles.css";
import { ApiError } from "./api/client";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { Loading } from "./components/States";
import { ToastProvider } from "./components/Toast";
import { UploadsProvider } from "./uploads/UploadsContext";
import { EventPage } from "./pages/EventPage";
import { FlightDetailPage } from "./pages/FlightDetailPage";
import { FlightsPage } from "./pages/FlightsPage";
import { AdminPage } from "./pages/AdminPage";
import { LabellingPage } from "./pages/LabellingPage";
import { ReportsPage } from "./pages/ReportsPage";
import { RoutesPage } from "./pages/RoutesPage";
import { WorkOrdersPage } from "./pages/WorkOrdersPage";
import { LoginPage } from "./pages/LoginPage";
import { MapPage } from "./pages/MapPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReviewPage } from "./pages/ReviewPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      // Don't retry auth / not-found errors.
      retry: (count, err) => !(err instanceof ApiError && [401, 403, 404].includes(err.status)) && count < 2,
    },
  },
});

function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="page state">
      <h1>{t("notFound.title")}</h1>
      <Link to="/" className="btn">
        {t("notFound.back")}
      </Link>
    </div>
  );
}

function App() {
  const { state } = useAuth();
  if (state.kind === "loading") return <Loading />;
  if (state.kind === "signedOut") return <LoginPage expired={state.reason === "expired"} />;
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="events/:eventId" element={<EventPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="flights" element={<FlightsPage />} />
        <Route path="flights/:flightId" element={<FlightDetailPage />} />
        <Route path="work-orders" element={<WorkOrdersPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="routes" element={<RoutesPage />} />
        <Route path="labelling" element={<LabellingPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="admin/:tab" element={<AdminPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/app">
        <ToastProvider>
          <AuthProvider>
            <UploadsProvider>
              <App />
            </UploadsProvider>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
