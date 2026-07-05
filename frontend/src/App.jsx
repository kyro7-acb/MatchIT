import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { MatchPage } from "./pages/MatchPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"    element={<LandingPage />} />
        <Route path="/app" element={<MatchPage />} />
      </Routes>
    </BrowserRouter>
  );
}