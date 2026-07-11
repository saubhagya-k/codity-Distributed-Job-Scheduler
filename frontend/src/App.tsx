import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }, [token]);

  // If token exists, go to dashboard; otherwise, redirect to login.
  // The main route '/' will redirect appropriately.
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login setToken={setToken} />} />
        <Route
          path="/dashboard/*"
          element={token ? <Dashboard /> : <Navigate to="/login" replace />}
        />
        <Route path="/" element={<Navigate to={token ? "/dashboard" : "/login"} replace />} />
        {/* Catch-all: redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;