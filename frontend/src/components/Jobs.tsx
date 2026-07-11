import React, { useEffect, useState } from 'react';
import api from '../api';
import { Table, TableHead, TableRow, TableCell, TableBody, Select, MenuItem, Button, TextField, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';

interface Job {
  id: string;
  name: string;
  status: string;
  job_type: string;
  created_at: string;
  target: string;
  queue_id: string;
}

const Jobs: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [filter, setFilter] = useState({ status: '', job_type: '', queue_id: '' });
  const [openCreate, setOpenCreate] = useState(false);
  const [newJob, setNewJob] = useState({ name: '', queue_id: '', target: '', payload: '{}' });
  const [queues, setQueues] = useState<{ id: string; name: string }[]>([]);

  const fetchJobs = async () => {
    const params = new URLSearchParams(filter);
    const res = await api.get(`/jobs/?${params}`);
    setJobs(res.data.items || []);
  };

  const fetchQueues = async () => {
    const res = await api.get('/queues/');
    setQueues(res.data);
  };

  const createJob = async () => {
    await api.post('/jobs/', { ...newJob, payload: JSON.parse(newJob.payload), job_type: 'immediate' });
    setOpenCreate(false);
    fetchJobs();
  };

  useEffect(() => {
    fetchJobs();
    fetchQueues();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  return (
    <div>
      <Button variant="contained" onClick={() => setOpenCreate(true)} sx={{ mb: 2 }}>Create Job</Button>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Target</TableCell>
            <TableCell>Created</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {jobs.map(j => (
            <TableRow key={j.id}>
              <TableCell>{j.name}</TableCell>
              <TableCell>{j.status}</TableCell>
              <TableCell>{j.job_type}</TableCell>
              <TableCell>{j.target}</TableCell>
              <TableCell>{new Date(j.created_at).toLocaleString()}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={openCreate} onClose={() => setOpenCreate(false)}>
        <DialogTitle>New Job</DialogTitle>
        <DialogContent>
          <TextField label="Name" fullWidth margin="dense" value={newJob.name} onChange={(e) => setNewJob({...newJob, name: e.target.value})} />
          <Select fullWidth value={newJob.queue_id} onChange={(e) => setNewJob({...newJob, queue_id: e.target.value})} displayEmpty>
            <MenuItem value="">Select Queue</MenuItem>
            {queues.map(q => <MenuItem key={q.id} value={q.id}>{q.name}</MenuItem>)}
          </Select>
          <TextField label="Target URL" fullWidth margin="dense" value={newJob.target} onChange={(e) => setNewJob({...newJob, target: e.target.value})} />
          <TextField label="Payload (JSON)" fullWidth margin="dense" value={newJob.payload} onChange={(e) => setNewJob({...newJob, payload: e.target.value})} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenCreate(false)}>Cancel</Button>
          <Button onClick={createJob} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default Jobs;