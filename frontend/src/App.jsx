import React from "react";
import { Route, Routes } from "react-router-dom";
import SinglePageSlider from "./components/slider/SinglePageSlider.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SinglePageSlider initialSlide={0} />} />
      <Route path="/analysis" element={<SinglePageSlider initialSlide={0} />} />
      <Route path="/ai-dashboard" element={<SinglePageSlider initialSlide={1} />} />
      <Route path="/dashboard" element={<SinglePageSlider initialSlide={2} />} />
      <Route path="/feedback" element={<SinglePageSlider initialSlide={3} />} />
      <Route path="*" element={<SinglePageSlider initialSlide={0} />} />
    </Routes>
  );
}