import React, { useEffect, useState } from 'react';
import api from '../api';
import { Table, TableHead, TableRow, TableCell, TableBody, Chip } from '@mui/material';

interface Worker {
  id: string;
  hostname: string;
  pid: string;
  status: string;
  last_heartbeat: string;
}

const Workers: React.FC = () => {
  const [workers, setWorkers] = useState<Worker[]>([]);

  const fetchWorkers = async () => {
    const res = await api.get('/workers/');
    setWorkers(res.data);
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableCell>Hostname</TableCell>
          <TableCell>PID</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Last Heartbeat</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {workers.map(w => (
          <TableRow key={w.id}>
            <TableCell>{w.hostname}</TableCell>
            <TableCell>{w.pid}</TableCell>
            <TableCell>
              <Chip label={w.status} color={w.status === 'active' ? 'success' : 'error'} />
            </TableCell>
            <TableCell>{new Date(w.last_heartbeat).toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

export default Workers;