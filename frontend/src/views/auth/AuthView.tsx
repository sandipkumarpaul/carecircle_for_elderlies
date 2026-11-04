import { useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Stack, Tab, Tabs, TextField, Typography } from '@mui/material';
import { api, refreshCsrf, setCsrfToken } from '../../lib/api';
import { User } from '../../lib/types';
export function AuthView({ onLogin, hasInvite }: { onLogin: (user: User) => void; hasInvite: boolean }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError('');
    try {
      await refreshCsrf();
      const result = await api<{ user: User; csrf_token: string }>(`/auth/${mode}`, { method: 'POST', body: JSON.stringify({ email: form.get('email'), password: form.get('password'), ...(mode === 'register' ? { display_name: form.get('display_name') } : {}) }) });
      setCsrfToken(result.csrf_token); onLogin(result.user);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 5, alignItems: 'center', py: 5 }}>
    <Stack spacing={3}><Typography variant="overline" color="primary">CARE, CONNECTED</Typography><Typography variant="h1">A little closer.<br />A little more care.</Typography>
      <Typography variant="h6" component="p" color="text.secondary">Bring the people you trust into one care circle. You decide who can see and manage each part of your care.</Typography>
      <Typography color="text.secondary">Your account is personal. Patient and caregiver access is assigned separately for each circle.</Typography></Stack>
    <Card variant="outlined"><CardContent sx={{ p: { xs: 3, sm: 4 } }}><Tabs value={mode} onChange={(_, value) => { setMode(value); setError(''); }} aria-label="Account access" sx={{ mb: 3 }}>
      <Tab value="login" label="Sign in" /><Tab value="register" label="Create account" /></Tabs>
      {hasInvite && <Alert severity="info" sx={{ mb: 2 }}>Sign in with the email address on your invitation to review and accept it.</Alert>}
      <Stack component="form" onSubmit={submit} spacing={2} key={mode}>
        {mode === 'register' && <TextField required name="display_name" label="Your name" autoComplete="name" inputProps={{ maxLength: 100 }} />}
        <TextField required name="email" type="email" label="Email address" autoComplete="email" inputProps={{ maxLength: 254 }} />
        <TextField required name="password" type="password" label="Password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} inputProps={{ minLength: mode === 'register' ? 12 : 1, maxLength: 128 }} helperText={mode === 'register' ? 'Use at least 12 characters.' : undefined} />
        {error && <Alert severity="error" role="alert">{error}</Alert>}<Button type="submit" variant="contained" size="large" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</Button>
      </Stack></CardContent></Card></Box>;
}
