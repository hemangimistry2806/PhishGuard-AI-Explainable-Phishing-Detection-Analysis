import React from "react";
import { Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout.jsx";

import HomePage from "./pages/Home/HomePage.jsx";
import AiDashboardPage from "./pages/AiDashboard/AiDashboardPage.jsx";
import DashboardPage from "./pages/Dashboard/DashboardPage.jsx";
import FeedbackPage from "./pages/Feedback/FeedbackPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="/ai-dashboard" element={<AiDashboardPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/feedback" element={<FeedbackPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}