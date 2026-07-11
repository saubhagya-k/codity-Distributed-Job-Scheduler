import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { Container, TextField, Button, Typography, Box, Alert } from '@mui/material';

interface LoginProps {
  setToken: (token: string) => void;
}

const Login: React.FC<LoginProps> = ({ setToken }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post('/auth/login', { email, password });
      setToken(res.data.access_token);
      navigate('/dashboard');
    } catch (err) {
      setError('Invalid credentials');
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 10 }}>
      <Typography variant="h4" gutterBottom>Job Scheduler</Typography>
      <Box component="form" onSubmit={handleSubmit}>
        <TextField fullWidth label="Email" value={email} onChange={(e) => setEmail(e.target.value)} margin="normal" required />
        <TextField fullWidth label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} margin="normal" required />
        {error && <Alert severity="error">{error}</Alert>}
        <Button type="submit" fullWidth variant="contained" sx={{ mt: 2 }}>Login</Button>
      </Box>
    </Container>
  );
};

export default Login;