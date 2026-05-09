import { Navigate, Route, Routes } from 'react-router-dom';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/profile" replace />} />
      <Route path="/login" element={<div>Login (TODO)</div>} />
      <Route path="/profile" element={<div>Profile (TODO)</div>} />
      <Route path="*" element={<Navigate to="/profile" replace />} />
    </Routes>
  );
}
