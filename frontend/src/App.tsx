import React from 'react';
import { Alert, AppBar, Box, Button, Container, MenuItem, Stack, TextField, Toolbar, Typography } from '@mui/material';
import { api, ApiError, refreshCsrf, setCsrfToken } from './lib/api';
import { Page, Patient, User } from './lib/types';
import { AuthView } from './views/auth/AuthView';
import { PatientForm } from './views/circle/PatientForm';
import { AcceptInvite } from './views/circle/AcceptInvite';
import { CircleView } from './views/circle/CircleView';
const initialInvite = new URLSearchParams(location.hash.slice(1)).get('invite') ?? '';

export default function App() {
  const [user, setUser] = React.useState<User | null>(null); const [loading, setLoading] = React.useState(true); const [error, setError] = React.useState('');
  const [page, setPage] = React.useState<Page<Patient>>({ items: [], total: 0, offset: 0, limit: 20 });
  const [selected, setSelected] = React.useState<Patient | null>(null); const [createOpen, setCreateOpen] = React.useState(false); const [notice, setNotice] = React.useState('');
  async function bootstrap() {
    setLoading(true); setError('');
    try { await refreshCsrf(); try { setUser(await api<User>('/auth/me')); } catch (e) { if (!(e instanceof ApiError && e.status === 401)) throw e; setUser(null); } }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }
  async function loadPatients(offset = 0, preferred?: string) {
    try { const result = await api<Page<Patient>>(`/patients?offset=${offset}&limit=20`); setPage(result); setSelected(old => result.items.find(p => p.id === (preferred ?? old?.id)) ?? result.items[0] ?? null); }
    catch (e) { setError((e as Error).message); if (e instanceof ApiError && e.status === 401) { setUser(null); setSelected(null); } }
  }
  React.useEffect(() => { void bootstrap(); }, []);
  React.useEffect(() => { if (user) void loadPatients(); else { setSelected(null); setPage({ items: [], total: 0, offset: 0, limit: 20 }); } }, [user?.id]);
  React.useEffect(() => {
    if (!user) return;
    const refresh = () => { if (!document.hidden) void loadPatients(page.offset); };
    const timer = window.setInterval(refresh, 30000); window.addEventListener('focus', refresh);
    return () => { clearInterval(timer); window.removeEventListener('focus', refresh); };
  }, [user?.id, page.offset]);
  async function logout() {
    try { await api('/auth/logout', { method: 'POST' }); setUser(null); setCsrfToken(null); setNotice(''); await refreshCsrf(); }
    catch (e) { setError((e as Error).message); }
  }
  return <><AppBar position="static" color="transparent" elevation={0} sx={{ borderBottom: '1px solid #dce6df' }}><Container maxWidth="lg"><Toolbar disableGutters sx={{ justifyContent: 'space-between', gap: 2 }}>
    <Typography color="primary" variant="h6" fontWeight={800}>CareCircle •</Typography>{user ? <Stack direction="row" alignItems="center" spacing={2}><Typography variant="body2">{user.display_name}</Typography><Button onClick={logout}>Sign out</Button></Stack> : <Typography variant="body2" color="text.secondary">Together in care</Typography>}
  </Toolbar></Container></AppBar><Container component="main" maxWidth="lg" sx={{ py: 4 }}>
    {error && <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>{error} <Button onClick={bootstrap}>Retry connection</Button></Alert>}
    {loading ? <Typography role="status">Opening CareCircle…</Typography> : !user ? <AuthView hasInvite={!!initialInvite} onLogin={u => { setUser(u); setError(''); }} /> : <Stack spacing={4}>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}><Box><Typography variant="h4" component="h1" fontWeight={700}>Your care circles</Typography><Typography color="text.secondary">People, permissions, and peace of mind.</Typography></Box><Button variant="outlined" onClick={() => setCreateOpen(true)}>Create patient profile</Button></Stack>
      {notice && <Alert severity="success" onClose={() => setNotice('')}>{notice}</Alert>}
      {page.items.length > 0 ? <><TextField select label="Patient profile" value={selected?.id ?? ''} onChange={e => setSelected(page.items.find(p => p.id === e.target.value) ?? null)} sx={{ maxWidth: 480 }}>{page.items.map(p => <MenuItem key={p.id} value={p.id}>{p.display_name} · {p.role}</MenuItem>)}</TextField>
        {selected && <CircleView key={selected.id} patient={selected} user={user} onAccessChanged={() => void loadPatients(page.offset)} />}</> : <Alert severity="info">You have no patient profiles on this page. Create your own profile or accept a caregiver invitation below.</Alert>}
      {page.total > 20 && <Stack direction="row" spacing={2}><Button disabled={!page.offset} onClick={() => loadPatients(page.offset - 20)}>Previous</Button><Typography>{page.offset + 1}–{Math.min(page.offset + 20, page.total)} of {page.total}</Typography><Button disabled={page.offset + 20 >= page.total} onClick={() => loadPatients(page.offset + 20)}>Next</Button></Stack>}
      <AcceptInvite initialToken={initialInvite} onAccepted={p => { setNotice(`You joined ${p.display_name}’s care circle.`); void loadPatients(0, p.id); }} />
    </Stack>}
    <Typography variant="body2" color="text.secondary" sx={{ mt: 6 }}>CSE470 · Sprint 1 · Care-circle access is available. Medicine, dose, and health-monitoring features will follow.</Typography>
  </Container>{createOpen && <PatientForm onClose={() => setCreateOpen(false)} onCreated={p => { setCreateOpen(false); setNotice('Patient profile created with consent.'); void loadPatients(0, p.id); }} />}</>;
}
