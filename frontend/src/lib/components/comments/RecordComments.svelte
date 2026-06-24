<script>
  import { invalidateAll } from '$app/navigation';
  import { deserialize } from '$app/forms';
  import { toast } from 'svelte-sonner';
  import { MessageSquare, Pencil, Trash2, Send, Loader2 } from '@lucide/svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import { MarkdownView } from '$lib/components/ui/markdown';
  import { getCurrentUser } from '$lib/api.js';
  import { formatRelativeDate } from '$lib/utils/formatting.js';

  /**
   * Comments for a record. Saves through the page's `addComment` /
   * `editComment` / `deleteComment` server actions (cookie JWT + org context),
   * renders comment text as Markdown, and gates edit/delete to the author or an
   * admin (the backend re-enforces this).
   * @type {{ comments?: any[], canComment?: boolean }}
   */
  let { comments = [], canComment = true } = $props();

  const user = getCurrentUser();
  const currentEmail = user?.email || user?.user?.email || user?.user_details?.email || '';
  const isAdmin = !!(user && (user.role === 'ADMIN' || user.is_admin || user.is_superuser));

  let newComment = $state('');
  let submitting = $state(false);
  let editingId = $state('');
  let editText = $state('');
  let savingEdit = $state(false);
  let busyId = $state('');
  let confirmId = $state('');

  /** @param {any} c */
  function authorEmail(c) {
    return c?.commented_by?.user_details?.email || c?.commented_by?.email || '';
  }
  /** @param {any} c */
  function authorName(c) {
    const e = authorEmail(c);
    return e ? e.split('@')[0].replace(/[._]/g, ' ') : 'Unknown';
  }
  /** @param {any} c */
  function canEdit(c) {
    return isAdmin || (!!currentEmail && authorEmail(c) === currentEmail);
  }

  /** @param {string} name @param {Record<string,string>} fields */
  async function runAction(name, fields) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    const res = await fetch(`?/${name}`, { method: 'POST', body: fd });
    /** @type {any} */
    const result = deserialize(await res.text());
    if (result.type === 'failure') throw new Error(result.data?.error || 'Action failed');
    if (result.type === 'error') throw new Error(result.error?.message || 'Action failed');
  }

  async function submitNew() {
    const text = newComment.trim();
    if (!text || submitting) return;
    submitting = true;
    try {
      await runAction('addComment', { comment: text });
      newComment = '';
      toast.success('Comment added');
      await invalidateAll();
    } catch (err) {
      toast.error(/** @type {any} */ (err)?.message || 'Failed to add comment');
    } finally {
      submitting = false;
    }
  }

  /** @param {any} c */
  function startEdit(c) {
    editingId = c.id;
    editText = c.comment || '';
  }
  function cancelEdit() {
    editingId = '';
    editText = '';
  }
  /** @param {any} c */
  async function saveEdit(c) {
    const text = editText.trim();
    if (!text || savingEdit) return;
    savingEdit = true;
    try {
      await runAction('editComment', { commentId: c.id, comment: text });
      toast.success('Comment updated');
      editingId = '';
      await invalidateAll();
    } catch (err) {
      toast.error(/** @type {any} */ (err)?.message || 'Failed to update comment');
    } finally {
      savingEdit = false;
    }
  }
  /** @param {string} id */
  async function doDelete(id) {
    busyId = id;
    try {
      await runAction('deleteComment', { commentId: id });
      toast.success('Comment deleted');
      confirmId = '';
      await invalidateAll();
    } catch (err) {
      toast.error(/** @type {any} */ (err)?.message || 'Failed to delete comment');
    } finally {
      busyId = '';
    }
  }

  const inputClass =
    'w-full rounded-md border border-[color:var(--border-strong,var(--border))] bg-[color:var(--bg)] px-3 py-2 text-[13px] text-[color:var(--text)] outline-none focus:border-[color:var(--color-primary-default,#2563eb)] resize-y';
</script>

<div class="flex flex-col gap-4">
  {#if canComment}
    <div class="flex flex-col gap-2">
      <textarea
        bind:value={newComment}
        rows="3"
        placeholder="Write a comment… Markdown supported (# H1, ## H2, **bold**, - lists)."
        class={inputClass}
        disabled={submitting}
      ></textarea>
      <div class="flex justify-end">
        <Button size="sm" onclick={submitNew} disabled={submitting || !newComment.trim()}>
          {#if submitting}<Loader2 class="mr-1.5 size-3.5 animate-spin" />{:else}<Send class="mr-1.5 size-3.5" />{/if}
          Comment
        </Button>
      </div>
    </div>
  {/if}

  {#if comments.length === 0}
    <p class="flex items-center gap-2 py-2 text-[13px] italic text-[color:var(--text-subtle)]">
      <MessageSquare class="size-3.5" /> No comments yet.
    </p>
  {:else}
    <ul class="flex flex-col divide-y divide-[color:var(--border)]/50">
      {#each comments as c (c.id)}
        <li class="py-3 first:pt-0">
          <div class="mb-1 flex items-center justify-between gap-2">
            <div class="flex items-baseline gap-2">
              <span class="text-[13px] font-medium capitalize text-[color:var(--text)]">{authorName(c)}</span>
              <span class="text-[11px] text-[color:var(--text-subtle)]">
                {c.commented_on ? formatRelativeDate(c.commented_on) : ''}
              </span>
            </div>
            {#if canEdit(c) && editingId !== c.id}
              <div class="flex items-center gap-0.5">
                <button
                  type="button"
                  onclick={() => startEdit(c)}
                  title="Edit comment"
                  aria-label="Edit comment"
                  class="rounded p-1 text-[color:var(--text-subtle)] hover:bg-[color:var(--bg-elevated)] hover:text-[color:var(--text)]"
                >
                  <Pencil class="size-3.5" />
                </button>
                <button
                  type="button"
                  onclick={() => (confirmId = c.id)}
                  title="Delete comment"
                  aria-label="Delete comment"
                  class="rounded p-1 text-[color:var(--text-subtle)] hover:bg-[color:var(--color-danger-light,#fee2e2)] hover:text-[color:var(--color-danger-default,#dc2626)]"
                >
                  <Trash2 class="size-3.5" />
                </button>
              </div>
            {/if}
          </div>

          {#if editingId === c.id}
            <div class="flex flex-col gap-2">
              <textarea bind:value={editText} rows="3" class={inputClass} disabled={savingEdit}></textarea>
              <div class="flex justify-end gap-2">
                <Button variant="outline" size="sm" onclick={cancelEdit} disabled={savingEdit}>Cancel</Button>
                <Button size="sm" onclick={() => saveEdit(c)} disabled={savingEdit || !editText.trim()}>
                  {#if savingEdit}<Loader2 class="mr-1.5 size-3.5 animate-spin" />{/if}Save
                </Button>
              </div>
            </div>
          {:else if confirmId === c.id}
            <div class="flex items-center justify-between gap-3 rounded-md bg-[color:var(--bg-elevated)] px-3 py-2">
              <span class="text-[12px] text-[color:var(--text-muted)]">Delete this comment?</span>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" onclick={() => (confirmId = '')} disabled={busyId === c.id}>Cancel</Button>
                <Button variant="destructive" size="sm" onclick={() => doDelete(c.id)} disabled={busyId === c.id}>
                  {#if busyId === c.id}<Loader2 class="mr-1.5 size-3.5 animate-spin" />{/if}Delete
                </Button>
              </div>
            </div>
          {:else}
            <MarkdownView value={c.comment} emptyText="(empty)" />
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>
