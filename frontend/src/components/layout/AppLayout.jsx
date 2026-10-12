import { Outlet } from "react-router-dom";
import Footer from "./Footer.jsx";
import Navbar from "./Navbar.jsx";

export default function AppLayout() {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="page-shell">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
