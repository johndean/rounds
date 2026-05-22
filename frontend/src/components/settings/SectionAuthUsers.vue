<script setup lang="ts">
/**
 * SectionAuthUsers — Settings → Auth & Logins.
 *
 * Reset-only model: passwords are bcrypt-hashed at rest and never displayed.
 * Operators can:
 *   • list all logins (email, role, status, last-login)
 *   • add a new user (email + initial password)
 *   • toggle role between admin/user
 *   • disable / re-enable (is_active)
 *   • reset password (admin types new plaintext, server hashes, response
 *     surfaces only password_reset_at — the plaintext never echoes back)
 *   • delete a user (refused for the last active admin)
 *
 * Backend: /v1/settings/auth-users (settings.py). All endpoints admin-gated.
 */
import { computed, onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import {
  diag,
  settingsApi,
  type AuthUser,
} from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

const users   = ref<AuthUser[]>([]);
const loading = ref(true);

// ── Add user inline form ────────────────────────────────────────────────
const newEmail    = ref('');
const newPassword = ref('');
const newRole     = ref<'admin' | 'user'>('user');
const adding      = ref(false);

// Live helper text under the Add form. Tells the operator EXACTLY why
// the button is disabled (or that it's ready) so a no-op click never
// looks like "the button doesn't work".
const addUserHint = computed(() => {
  if (!newEmail.value) return 'Enter an email to begin.';
  if (!newPassword.value) return 'Enter an initial password (min 12 chars).';
  if (newPassword.value.length < 12) {
    return `Password is ${newPassword.value.length} chars — need at least 12.`;
  }
  return 'Ready. Share the password out-of-band (1Password, Slack DM, etc.) — the user can\'t see it later.';
});
const addUserReady = computed(() =>
  newEmail.value.length > 0 &&
  newPassword.value.length >= 12,
);

// ── Empty-state recovery (re-seed from AUTH_USERS env) ─────────────────
// Surfaced inline when the user list is empty so the operator has a
// one-click path out of the "0 logins · 0 active admins" dead-end the
// cutover left behind on 2026-05-21.
const reseeding  = ref(false);
const lastReseed = ref<{ seeded: number; total: number; skipped_count: number } | null>(null);

// ── Reset-password modal state ──────────────────────────────────────────
const resetTargetId    = ref<string | null>(null);
const resetTargetEmail = ref<string>('');
const resetPassword    = ref<string>('');
const resetSaving      = ref(false);

// ── Per-row busy state so action buttons don't double-fire ─────────────
const busyIds = ref<Set<string>>(new Set());
const isBusy = (id: string) => busyIds.value.has(id);

function setBusy(id: string, on: boolean) {
  const next = new Set(busyIds.value);
  if (on) next.add(id); else next.delete(id);
  busyIds.value = next;
}

async function hydrate(): Promise<void> {
  loading.value = true;
  try {
    users.value = await settingsApi.authUsersList();
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0;
    if (status === 403) {
      toast.push('Admin only — your account does not have access to Auth & Logins.', { tone: 'error' });
    } else {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : (e as Error).message;
      toast.push(`Failed to load users: ${msg}`, { tone: 'error' });
    }
    users.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(hydrate);

// ── ApiError → friendly toast (matches SectionTeam pattern) ────────────
function surfaceError(e: unknown, fallback: string) {
  if (e instanceof ApiError && e.body && typeof e.body === 'object') {
    const body = e.body as { detail?: { code?: string; message?: string } | string };
    const detail = body.detail;
    if (detail && typeof detail === 'object' && detail.message) {
      toast.push(detail.message, { tone: 'error' });
      return;
    }
    if (typeof detail === 'string') {
      toast.push(detail, { tone: 'error' });
      return;
    }
  }
  const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : (e instanceof Error ? e.message : fallback);
  toast.push(msg, { tone: 'error' });
}

// ── Add ────────────────────────────────────────────────────────────────
async function addUser(): Promise<void> {
  const email = newEmail.value.trim().toLowerCase();
  const password = newPassword.value;
  if (!email || !password) {
    toast.push('Email and password are both required.', { tone: 'warn' });
    return;
  }
  if (password.length < 12) {
    toast.push('Password must be at least 12 characters.', { tone: 'warn' });
    return;
  }
  adding.value = true;
  try {
    const row = await settingsApi.authUsersAdd({ email, password, role: newRole.value });
    users.value = [...users.value, row].sort((a, b) => a.email.localeCompare(b.email));
    newEmail.value    = '';
    newPassword.value = '';
    newRole.value     = 'user';
    toast.push(`Added ${row.email}`, { tone: 'success' });
  } catch (e) {
    surfaceError(e, 'Failed to add user');
  } finally {
    adding.value = false;
  }
}

// ── Toggle role ────────────────────────────────────────────────────────
async function toggleRole(u: AuthUser): Promise<void> {
  const next = u.role === 'admin' ? 'user' : 'admin';
  setBusy(u.id, true);
  try {
    const row = await settingsApi.authUsersUpdate(u.id, { role: next });
    users.value = users.value.map((x) => (x.id === u.id ? row : x));
    toast.push(`${row.email} is now ${row.role}`, { tone: 'success' });
  } catch (e) {
    surfaceError(e, 'Failed to update role');
  } finally {
    setBusy(u.id, false);
  }
}

// ── Toggle active ──────────────────────────────────────────────────────
async function toggleActive(u: AuthUser): Promise<void> {
  setBusy(u.id, true);
  try {
    const row = await settingsApi.authUsersUpdate(u.id, { is_active: !u.is_active });
    users.value = users.value.map((x) => (x.id === u.id ? row : x));
    toast.push(`${row.email} ${row.is_active ? 're-enabled' : 'disabled'}`, { tone: 'success' });
  } catch (e) {
    surfaceError(e, 'Failed to update status');
  } finally {
    setBusy(u.id, false);
  }
}

// ── Reset password modal ───────────────────────────────────────────────
function openReset(u: AuthUser): void {
  resetTargetId.value    = u.id;
  resetTargetEmail.value = u.email;
  resetPassword.value    = '';
}
function closeReset(): void {
  resetTargetId.value    = null;
  resetTargetEmail.value = '';
  resetPassword.value    = '';
  resetSaving.value      = false;
}
async function submitReset(): Promise<void> {
  if (!resetTargetId.value) return;
  if (resetPassword.value.length < 12) {
    toast.push('Password must be at least 12 characters.', { tone: 'warn' });
    return;
  }
  resetSaving.value = true;
  try {
    const res = await settingsApi.authUsersResetPassword(resetTargetId.value, resetPassword.value);
    // Patch the row locally so the password_reset_at column reflects immediately.
    users.value = users.value.map((u) =>
      u.id === resetTargetId.value ? { ...u, password_reset_at: res.password_reset_at } : u,
    );
    toast.push(`Password reset for ${res.email}`, { tone: 'success' });
    closeReset();
  } catch (e) {
    surfaceError(e, 'Failed to reset password');
  } finally {
    resetSaving.value = false;
  }
}

// ── Delete ─────────────────────────────────────────────────────────────
async function deleteUser(u: AuthUser): Promise<void> {
  const ok = await confirm.open({
    title: 'Delete login?',
    body: `${u.email} will lose access immediately. This cannot be undone.`,
    confirmLabel: 'Delete',
    danger: true,
  });
  if (!ok) return;
  setBusy(u.id, true);
  try {
    await settingsApi.authUsersRemove(u.id);
    users.value = users.value.filter((x) => x.id !== u.id);
    toast.push(`Deleted ${u.email}`, { tone: 'success' });
  } catch (e) {
    surfaceError(e, 'Failed to delete user');
  } finally {
    setBusy(u.id, false);
  }
}

// ── Pretty-print helpers ───────────────────────────────────────────────
function fmtTs(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

const activeAdminCount = computed(
  () => users.value.filter((u) => u.role === 'admin' && u.is_active).length,
);

// ── Reseed from AUTH_USERS env (admin-only, idempotent) ────────────────
async function reseedFromEnv(): Promise<void> {
  if (reseeding.value) return;
  reseeding.value = true;
  try {
    const r = await diag.reseedAuthUsers();
    lastReseed.value = r;
    if (r.seeded > 0) {
      toast.push(`Seeded ${r.seeded} login${r.seeded === 1 ? '' : 's'} from AUTH_USERS env.`, { tone: 'success' });
      await hydrate();
    } else if (r.total === 0) {
      toast.push('Seed produced 0 rows — AUTH_USERS env may be empty or all rows tripped bcrypt.', { tone: 'warn' });
    } else {
      toast.push(`Table already has ${r.total} row${r.total === 1 ? '' : 's'}; seed was a no-op.`, { tone: 'info' });
      await hydrate();
    }
  } catch (e) {
    surfaceError(e, 'Reseed failed');
  } finally {
    reseeding.value = false;
  }
}
</script>

<template>
  <SettingsHeader
    title="Auth & Logins"
    lead="Manage who can sign in. Passwords are bcrypt-hashed at rest and never shown. Use Reset to set a new one."
  />

  <div v-if="loading" class="set-card-block" :style="{ padding: '40px', textAlign: 'center', color: 'var(--fg2)' }">
    Loading users…
  </div>

  <template v-else>
    <!-- Add user inline form -->
    <div class="set-card-block">
      <div class="set-eyebrow">ADD LOGIN</div>
      <div :style="{ display: 'grid', gridTemplateColumns: '1.6fr 1.6fr 0.8fr auto', gap: '8px', marginTop: '8px' }">
        <input
          v-model="newEmail"
          type="email"
          placeholder="email@vin.com"
          autocomplete="off"
          data-test-id="auth-users-new-email"
          :style="{ padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--surface)', color: 'var(--fg1)', fontSize: '13px' }"
        />
        <input
          v-model="newPassword"
          type="password"
          placeholder="initial password (min 12 chars)"
          autocomplete="new-password"
          data-test-id="auth-users-new-password"
          :style="{ padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--surface)', color: 'var(--fg1)', fontSize: '13px' }"
        />
        <select
          v-model="newRole"
          data-test-id="auth-users-new-role"
          :style="{ padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--surface)', color: 'var(--fg1)', fontSize: '13px' }"
        >
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <button
          class="btn btn--primary"
          :disabled="adding || !addUserReady"
          data-test-id="auth-users-add"
          @click="addUser"
        >{{ adding ? 'Adding…' : 'Add user' }}</button>
      </div>
      <div
        :style="{
          fontSize: '11px',
          marginTop: '6px',
          color: addUserReady ? 'var(--fg2)' : 'var(--color-warn, #b45309)',
        }"
        data-test-id="auth-users-hint"
      >{{ addUserHint }}</div>
    </div>

    <!-- Empty-state recovery panel: only when the table is truly empty.
         Gives the operator a one-click path out of the cutover dead-end
         where the boot-time seed failed and left auth_users with 0 rows. -->
    <div
      v-if="users.length === 0"
      class="set-card-block"
      :style="{
        border: '1px dashed var(--color-warn, #b45309)',
        background: 'rgba(245,158,11,0.04)',
      }"
    >
      <div :style="{ fontSize: '14px', fontWeight: 700, color: 'var(--fg1)', marginBottom: '4px' }">
        No logins in the database
      </div>
      <p :style="{ fontSize: '13px', color: 'var(--fg2)', margin: '0 0 12px', lineHeight: 1.5 }">
        The <code>auth_users</code> table is empty. Either this is a fresh install (add a login above),
        or the boot-time seed from <code>AUTH_USERS</code> didn't complete (e.g. a long password
        tripped bcrypt's 72-byte limit). You can re-run the seed now without redeploying — it's
        idempotent, so it's safe to click more than once.
      </p>
      <button
        class="btn btn--tertiary"
        :disabled="reseeding"
        data-test-id="auth-users-reseed"
        @click="reseedFromEnv"
      >{{ reseeding ? 'Reseeding…' : 'Seed from AUTH_USERS env' }}</button>
      <span
        v-if="lastReseed"
        :style="{ fontSize: '11px', color: 'var(--fg2)', marginLeft: '10px', fontFamily: 'var(--font-mono)' }"
      >
        last: seeded={{ lastReseed.seeded }} · total={{ lastReseed.total }} · skipped={{ lastReseed.skipped_count }}
      </span>
    </div>

    <!-- User list -->
    <div class="set-card-block">
      <div class="set-eyebrow">{{ users.length }} LOGIN{{ users.length === 1 ? '' : 'S' }} · {{ activeAdminCount }} ACTIVE ADMIN{{ activeAdminCount === 1 ? '' : 'S' }}</div>
      <table
        v-if="users.length > 0"
        :style="{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', marginTop: '8px' }"
      >
        <thead>
          <tr :style="{ borderBottom: '1px solid var(--border)', color: 'var(--fg2)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '.04em' }">
            <th :style="{ padding: '8px 6px', textAlign: 'left' }">Email</th>
            <th :style="{ padding: '8px 6px', textAlign: 'left' }">Role</th>
            <th :style="{ padding: '8px 6px', textAlign: 'left' }">Status</th>
            <th :style="{ padding: '8px 6px', textAlign: 'left' }">Last login</th>
            <th :style="{ padding: '8px 6px', textAlign: 'left' }">Password set</th>
            <th :style="{ padding: '8px 6px', textAlign: 'right' }">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="u in users"
            :key="u.id"
            :data-test-id="`auth-user-row-${u.email}`"
            :style="{ borderBottom: '1px solid var(--border-faint, var(--border))' }"
          >
            <td :style="{ padding: '10px 6px', fontFamily: 'var(--font-mono)' }">{{ u.email }}</td>
            <td :style="{ padding: '10px 6px' }">
              <span :class="`chip chip--${u.role === 'admin' ? 'amber' : 'ghost'}`" :style="{ fontSize: '10px' }">{{ u.role }}</span>
            </td>
            <td :style="{ padding: '10px 6px' }">
              <span :class="`chip chip--${u.is_active ? 'teal' : 'ghost'}`" :style="{ fontSize: '10px' }">{{ u.is_active ? 'active' : 'disabled' }}</span>
            </td>
            <td :style="{ padding: '10px 6px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)', fontSize: '11px' }">{{ fmtTs(u.last_login_at) }}</td>
            <td :style="{ padding: '10px 6px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)', fontSize: '11px' }">{{ fmtTs(u.password_reset_at || u.created_at) }}</td>
            <td :style="{ padding: '10px 6px', textAlign: 'right', whiteSpace: 'nowrap' }">
              <button
                class="btn btn--ghost btn--sm"
                :disabled="isBusy(u.id)"
                :data-test-id="`auth-user-reset-${u.email}`"
                @click="openReset(u)"
              >Reset password</button>
              <button
                class="btn btn--ghost btn--sm"
                :disabled="isBusy(u.id)"
                :style="{ marginLeft: '4px' }"
                :data-test-id="`auth-user-role-${u.email}`"
                @click="toggleRole(u)"
              >{{ u.role === 'admin' ? 'Make user' : 'Make admin' }}</button>
              <button
                class="btn btn--ghost btn--sm"
                :disabled="isBusy(u.id)"
                :style="{ marginLeft: '4px' }"
                :data-test-id="`auth-user-active-${u.email}`"
                @click="toggleActive(u)"
              >{{ u.is_active ? 'Disable' : 'Enable' }}</button>
              <button
                class="btn btn--ghost btn--sm"
                :disabled="isBusy(u.id)"
                :style="{ marginLeft: '4px', color: 'var(--color-error, #c44)' }"
                :data-test-id="`auth-user-delete-${u.email}`"
                @click="deleteUser(u)"
              >Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Reset password modal -->
    <div
      v-if="resetTargetId"
      :style="{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }"
      @click.self="closeReset"
    >
      <div :style="{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '24px', width: '420px', maxWidth: '90vw' }">
        <h3 :style="{ margin: '0 0 6px', fontSize: '16px', fontWeight: 700 }">Reset password</h3>
        <p :style="{ fontSize: '13px', color: 'var(--fg2)', margin: '0 0 16px' }">
          New password for <code>{{ resetTargetEmail }}</code>. Share it out-of-band — it won't be shown again.
        </p>
        <input
          v-model="resetPassword"
          type="password"
          placeholder="new password (min 12 chars)"
          autocomplete="new-password"
          data-test-id="auth-users-reset-password"
          :style="{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--bg)', color: 'var(--fg1)', fontSize: '13px', fontFamily: 'var(--font-mono)' }"
          @keydown.enter="submitReset"
        />
        <div :style="{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '16px' }">
          <button class="btn btn--ghost" :disabled="resetSaving" @click="closeReset">Cancel</button>
          <button
            class="btn btn--primary"
            :disabled="resetSaving || resetPassword.length < 12"
            data-test-id="auth-users-reset-submit"
            @click="submitReset"
          >{{ resetSaving ? 'Resetting…' : 'Reset password' }}</button>
        </div>
      </div>
    </div>
  </template>
</template>
