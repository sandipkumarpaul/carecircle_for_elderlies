import React from 'react';
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import type { Medicine } from './MedicineView';

type Draft = { id: string; locked: boolean; raw_text: string; reviewed_text: string; recognition_status: string; confidence: string | null; reviewed_at: string | null; edit_revision: number; suggestions: { medicine: Medicine; match_score: number }[] };
type List = { items: { id: string; recognition_status: string; created_at: string; reviewed_at: string | null }[]; total: number; offset: number; limit: number };

export function PrescriptionOCR({ patientId, canWrite, onChoose }: { patientId: string; canWrite: boolean; onChoose: (m: Medicine, draftId: string) => void }) {
  const [file, setFile] = React.useState<File | null>(null); const [draft, setDraft] = React.useState<Draft | null>(null);
  const [text, setText] = React.useState(''); const [error, setError] = React.useState(''); const [busy, setBusy] = React.useState(false);
  const [list, setList] = React.useState<List>({ items: [], total: 0, offset: 0, limit: 10 });
  const path = `/patients/${patientId}/ocr`;
  function open(value: Draft) { setDraft(value); setText(value.reviewed_text); }
  async function load(offset = 0) { setList(await api<List>(`${path}?offset=${offset}`)); }
  async function act(fn: () => Promise<void>) { setBusy(true); setError(''); try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  React.useEffect(() => { void act(() => load()); }, [patientId]);
  return <Stack spacing={2}>
    <Typography component="h3" variant="h6">Read a printed prescription image</Typography>
    <Typography variant="body2">Upload a clear English printed JPEG or PNG, up to 5 MB and 12 megapixels. Handwriting is not reliably supported. OCR can make mistakes: correct the text, choose the exact catalogue medicine, then enter dose instructions yourself. Recognition never confirms a prescription or creates doses. The image is discarded after processing.</Typography>
    {error && <Alert severity="error">{error} You can still use the catalogue and manual medicine entry below.</Alert>}
    {canWrite && <><Button component="label" variant="outlined" disabled={busy}>Choose prescription image<input data-testid="prescription-image" hidden type="file" accept="image/png,image/jpeg" onChange={e => { const selected = e.target.files?.[0] ?? null; setError(''); if (selected && selected.size > 5 * 1024 * 1024) { setError('Image must be at most 5 MB'); setFile(null); } else setFile(selected); }} /></Button>
      {file && <Typography sx={{ overflowWrap: 'anywhere' }}>{file.name}</Typography>}
      <Button disabled={busy || !file} onClick={() => void act(async () => { open(await api<Draft>(path, { method: 'POST', headers: { 'Content-Type': file!.type }, body: file! })); await load(); })}>{busy ? 'Processing…' : 'Extract prescription text'}</Button></>}
    {draft && <Box><Stack spacing={2}>
      <Typography>Recognition: {draft.recognition_status.replaceAll('_', ' ')}{draft.confidence !== null ? ` · OCR confidence ${draft.confidence}% (not medicine accuracy)` : ''}</Typography>
      {draft.recognition_status !== 'recognized' && <Alert severity="warning">Recognition is uncertain or empty. Try a clearer photo or type the prescription text manually.</Alert>}
      <TextField label="Extracted text (original)" value={draft.raw_text} multiline minRows={2} maxRows={8} slotProps={{ input: { readOnly: true } }} />
      <TextField label="Reviewed prescription text" value={text} onChange={e => setText(e.target.value)} disabled={!canWrite || busy || draft.locked} multiline minRows={3} maxRows={12} slotProps={{ htmlInput: { maxLength: 20000 } }} />
      {canWrite && !draft.locked && <Button disabled={busy || !text.trim()} onClick={() => void act(async () => { open(await api<Draft>(`${path}/${draft.id}`, { method: 'PUT', body: JSON.stringify({ reviewed_text: text, expected_revision: draft.edit_revision }) })); await load(); })}>Save reviewed text</Button>}
      {draft.reviewed_at && text === draft.reviewed_text && <Alert severity="success">Reviewed text saved. Verify each catalogue suggestion before choosing it.</Alert>}
      {draft.locked && <Typography>This reviewed text is preserved with a confirmed prescription version. Upload another image to make a new OCR draft.</Typography>}
      <Typography fontWeight={700}>Possible catalogue matches</Typography>
      {draft.suggestions.map(s => <Box key={s.medicine.id}><Typography>{s.medicine.brand_name} · {s.medicine.strength} · {s.medicine.form}</Typography><Typography variant="body2">{s.medicine.generic_name} · name similarity {Math.round(s.match_score * 100)}%</Typography>{canWrite && <Button disabled={busy || !draft.reviewed_at || text !== draft.reviewed_text} onClick={() => onChoose(s.medicine, draft.id)}>Use suggestion: {s.medicine.brand_name}</Button>}</Box>)}
      {!draft.suggestions.length && <Typography>No catalogue match found. Search manually; an administrator can add a verified reference entry if needed.</Typography>}
    </Stack></Box>}
    <Typography fontWeight={700}>Saved OCR drafts</Typography>
    {list.items.map(d => <Button key={d.id} disabled={busy} onClick={() => void act(async () => open(await api<Draft>(`${path}/${d.id}`)))}>Open draft · {new Date(d.created_at).toLocaleString()} · {d.reviewed_at ? 'Reviewed' : 'Needs review'}</Button>)}
    <Stack direction="row"><Button disabled={busy || !list.offset} onClick={() => void act(() => load(list.offset - 10))}>Previous drafts</Button><Button disabled={busy || list.offset + 10 >= list.total} onClick={() => void act(() => load(list.offset + 10))}>Next drafts</Button></Stack>
  </Stack>;
}
