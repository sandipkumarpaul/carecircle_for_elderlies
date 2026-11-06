export type User = { id: string; display_name: string; email: string; is_admin: boolean };
export type Patient = { id: string; display_name: string; timezone: string; role: 'patient' | 'primary' | 'secondary'; scopes: string[]; can_manage: boolean };
export type Grant = { role: 'primary' | 'secondary'; scopes: string[] };
export type Member = Grant & { id: string; user_id: string; display_name: string; email: string; revoked_at: string | null; accepted_at: string };
export type Invitation = Grant & { id: string; email: string; expires_at: string; accepted_at: string | null; revoked_at: string | null; patient_name?: string };
export type Circle = { patient: Patient; members: Member[]; invitations: Invitation[] };
export type Page<T> = { items: T[]; total: number; offset: number; limit: number };
export const scopeLabels: Record<string, string> = {
  'medicines:read': 'View medicines', 'medicines:write': 'Manage medicines',
  'adherence:read': 'View dose history', 'adherence:write': 'Record dose responses',
  'vitals:read': 'View vitals', 'vitals:write': 'Record vitals',
  'symptoms:read': 'View symptoms', 'symptoms:write': 'Record symptoms',
  'appointments:read': 'View appointments', 'appointments:write': 'Manage appointments',
  'tasks:read': 'View family tasks', 'tasks:write': 'Manage family tasks',
  'alerts:read': 'View alerts', 'alerts:write': 'Respond to alerts',
  'location:read': 'View shared location', 'summary:read': 'View doctor summaries',
  'summary:create': 'Create doctor summaries', 'circle:manage': 'Manage care circle',
  'privacy:manage': 'Manage privacy controls',
};
