<script>
  import { invalidateAll } from '$app/navigation';
  import { deserialize } from '$app/forms';
  import { Paperclip, Upload, Trash2, Loader2 } from '@lucide/svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import { toast } from 'svelte-sonner';
  import { formatRelativeDate } from '$lib/utils/formatting.js';
  import { accounts, leads, contacts, opportunities, tickets, getCurrentUser } from '$lib/api.js';

  /**
   * Upload / list / delete file attachments for a CRM record.
   * @type {{ entity: 'leads'|'contacts'|'accounts'|'opportunities'|'tickets', recordId: string, attachments?: any[] }}
   */
  let { entity, recordId, attachments = [] } = $props();

  const APIS = { leads, contacts, accounts, opportunities, tickets };
  const api = APIS[entity];

  // Client-side mirror of backend limits (backend/common/validators.py).
  // The server re-validates; this is for fast feedback only.
  const MAX_SIZE = 10 * 1024 * 1024;
  const ALLOWED = new Set([
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'txt',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'zip'
  ]);
  const BLOCKED = new Set([
    'exe', 'msi', 'bat', 'cmd', 'com', 'scr', 'pif', 'dll', 'sh', 'bash', 'zsh',
    'ps1', 'psm1', 'vbs', 'vbe', 'js', 'jse', 'jar', 'app', 'apk', 'deb', 'rpm',
    'bin', 'run', 'php', 'phtml', 'py', 'pl', 'rb', 'html', 'htm', 'svg'
  ]);
  const ACCEPT = Array.from(ALLOWED).map((e) => '.' + e).join(',');

  const user = getCurrentUser();
  const isAdmin = !!(user && (user.role === 'ADMIN' || user.is_admin));
  const userId = user?.id || user?.user_id || user?.user?.id;

  let uploading = $state(false);
  let deletingId = $state('');
  /** @type {HTMLInputElement | undefined} */
  let fileInput;

  /** @param {any} att */
  function canDelete(att) {
    if (isAdmin) return true;
    if (!userId) return false;
    const owner = att.created_by?.id ?? att.created_by;
    return owner === userId;
  }

  /** @param {File} file */
  function validate(file) {
    const segs = file.name.toLowerCase().split('.').slice(1);
    const ext = segs[segs.length - 1] || '';
    if (!ALLOWED.has(ext)) return `File type ".${ext || '?'}" is not allowed.`;
    if (segs.slice(0, -1).some((s) => BLOCKED.has(s))) {
      return 'Suspicious multi-extension file name is not allowed.';
    }
    if (file.size > MAX_SIZE) return 'File too large. Maximum size is 10 MB.';
    return null;
  }

  /** @param {Event} e */
  async function onFileChange(e) {
    const input = /** @type {HTMLInputElement} */ (e.currentTarget);
    const file = input.files?.[0];
    if (!file) return;
    const err = validate(file);
    if (err) {
      toast.error(err);
      input.value = '';
      return;
    }
    uploading = true;
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('?/uploadAttachment', { method: 'POST', body: fd });
      /** @type {any} */
      const result = deserialize(await res.text());
      if (result.type === 'failure') throw new Error(result.data?.error || 'Upload failed');
      if (result.type === 'error') throw new Error(result.error?.message || 'Upload failed');
      toast.success(`Uploaded ${file.name}`);
      await invalidateAll();
    } catch (/** @type {any} */ err2) {
      toast.error(err2?.message || 'Upload failed');
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  /** @param {any} att */
  async function onDelete(att) {
    if (!confirm(`Delete "${att.file_name || 'this file'}"? This cannot be undone.`)) return;
    deletingId = att.id;
    try {
      const fd = new FormData();
      fd.append('attachmentId', att.id);
      const res = await fetch('?/deleteAttachment', { method: 'POST', body: fd });
      /** @type {any} */
      const result = deserialize(await res.text());
      if (result.type === 'failure') throw new Error(result.data?.error || 'Delete failed');
      if (result.type === 'error') throw new Error(result.error?.message || 'Delete failed');
      toast.success('Attachment deleted');
      await invalidateAll();
    } catch (/** @type {any} */ err) {
      toast.error(err?.message || 'Delete failed');
    } finally {
      deletingId = '';
    }
  }
</script>

<div class="flex flex-col gap-3">
  <div class="flex items-center justify-between">
    <span class="text-[12px] font-medium text-[color:var(--text)]">
      Attachments{attachments.length ? ` (${attachments.length})` : ''}
    </span>
    <Button variant="outline" size="sm" disabled={uploading} onclick={() => fileInput?.click()}>
      {#if uploading}
        <Loader2 class="size-3.5 animate-spin" />
      {:else}
        <Upload class="size-3.5" />
      {/if}
      Upload
    </Button>
    <input
      bind:this={fileInput}
      type="file"
      accept={ACCEPT}
      class="hidden"
      disabled={uploading}
      onchange={onFileChange}
    />
  </div>

  {#if attachments.length === 0}
    <p class="text-[12px] italic text-[color:var(--text-subtle)]">
      No files uploaded. Max 10 MB; documents, images and zip files.
    </p>
  {:else}
    <ul class="flex flex-col divide-y divide-[color:var(--border-faint)]">
      {#each attachments as a (a.id)}
        <li class="flex items-center gap-3 py-2.5 text-[12px]">
          <Paperclip class="size-3.5 shrink-0 text-[color:var(--text-subtle)]" />
          <!-- TODO(security): file_path is served from /media/ without auth;
               anyone with the URL can fetch it. Move to an authenticated proxy
               or signed URLs (tracked separately). -->
          <a
            href={a.file_path}
            target="_blank"
            rel="noopener noreferrer"
            class="flex-1 truncate text-[color:var(--text)] hover:underline"
          >
            {a.file_name || 'File'}
          </a>
          <span class="text-[11px] text-[color:var(--text-subtle)]">
            {a.created_at
              ? formatRelativeDate(a.created_at)
              : a.created_on
                ? formatRelativeDate(a.created_on)
                : ''}
          </span>
          {#if canDelete(a)}
            <button
              type="button"
              class="text-[color:var(--text-subtle)] transition-colors hover:text-red-600 disabled:opacity-50"
              disabled={deletingId === a.id}
              onclick={() => onDelete(a)}
              aria-label="Delete attachment"
            >
              {#if deletingId === a.id}
                <Loader2 class="size-3.5 animate-spin" />
              {:else}
                <Trash2 class="size-3.5" />
              {/if}
            </button>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>
