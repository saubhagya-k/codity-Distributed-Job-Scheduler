import React, { useEffect, useState } from 'react';
import api from '../api';
import { Table, TableHead, TableRow, TableCell, TableBody, Button, Chip } from '@mui/material';

interface Queue {
  id: string;
  name: string;
  is_paused: boolean;
  concurrency_limit: number;
  priority: number;
}

const Queues: React.FC = () => {
  const [queues, setQueues] = useState<Queue[]>([]);

  const fetchQueues = async () => {
    const res = await api.get('/queues/');
    setQueues(res.data);
  };

  const togglePause = async (id: string, paused: boolean) => {
    const action = paused ? 'resume' : 'pause';
    await api.post(`/queues/${id}/${action}`);
    fetchQueues();
  };

  useEffect(() => {
    fetchQueues();
    const interval = setInterval(fetchQueues, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableCell>Name</TableCell>
          <TableCell>Concurrency</TableCell>
          <TableCell>Priority</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Action</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {queues.map(q => (
          <TableRow key={q.id}>
            <TableCell>{q.name}</TableCell>
            <TableCell>{q.concurrency_limit}</TableCell>
            <TableCell>{q.priority}</TableCell>
            <TableCell>
              <Chip label={q.is_paused ? 'Paused' : 'Active'} color={q.is_paused ? 'error' : 'success'} />
            </TableCell>
            <TableCell>
              <Button variant="outlined" size="small" onClick={() => togglePause(q.id, q.is_paused)}>
                {q.is_paused ? 'Resume' : 'Pause'}
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

export default Queues;