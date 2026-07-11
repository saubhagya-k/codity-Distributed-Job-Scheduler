import React from 'react';
import { Routes, Route, Link, useNavigate } from 'react-router-dom';
import { AppBar, Tabs, Tab, Box, Container, Button } from '@mui/material';
import Queues from './Queues';
import Jobs from './Jobs';
import Workers from './Workers';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <>
      <AppBar position="static">
        <Container>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Tabs value={location.pathname} onChange={(_, val) => navigate(val)}>
              <Tab label="Queues" value="/dashboard/queues" />
              <Tab label="Jobs" value="/dashboard/jobs" />
              <Tab label="Workers" value="/dashboard/workers" />
            </Tabs>
            <Button color="inherit" onClick={handleLogout} sx={{ ml: 'auto' }}>
              Logout
            </Button>
          </Box>
        </Container>
      </AppBar>
      <Container sx={{ mt: 3 }}>
        <Routes>
          <Route path="queues" element={<Queues />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="workers" element={<Workers />} />
          <Route path="*" element={<Queues />} /> {/* default tab */}
        </Routes>
      </Container>
    </>
  );
};

export default Dashboard;