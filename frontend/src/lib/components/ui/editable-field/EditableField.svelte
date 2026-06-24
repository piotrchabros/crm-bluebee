<script>
  import { invalidateAll } from '$app/navigation';
  import { deserialize } from '$app/forms';
  import { toast } from 'svelte-sonner';
  import { Pencil, Loader2 } from '@lucide/svelte';
  import { cn } from '$lib/utils.js';
  import MarkdownView from '$lib/components/ui/markdown/MarkdownView.svelte';

  /**
   * Inline, per-field editable value with autosave via a partial PATCH.
   *
   * On commit (blur / Enter), calls `api.patch(recordId, { [field]: value })`.
   * Success -> toast + invalidateAll (re-pulls canonical data). Failure ->
   * toast + revert (the `value` prop is the source of truth and is unchanged).
   *
   * @type {{
   *   value?: any,
   *   field: string,
   *   recordId: string,
   *   api: { patch: (id: string, data: Record<string, any>) => Promise<any> },
   *   type?: 'text'|'email'|'tel'|'url'|'number'|'date'|'textarea'|'markdown'|'select',
   *   options?: Array<{ value: string, label: string }>,
   *   readOnly?: boolean,
   *   placeholder?: string,
   *   emptyText?: string,
   *   format?: (value: any) => string,
   *   transform?: (raw: any) => any,
   *   onsaved?: () => void,
   *   class?: string,
   * }}
   */
  let {
    value = '',
    field,
    recordId,
    api,
    type = 'text',
    options = [],
    readOnly = false,
    placeholder = '',
    emptyText = '—',
    format,
    transform,
    onsaved,
    class: className = ''
  } = $props();

  let editing = $state(false);
  let saving = $state(false);
  let draft = $state('');
  /** @type {any} */
  let inputEl = $state(null);

  const isEmpty = $derived(value === null || value === undefined || value === '');
  const display = $derived(
    isEmpty ? '' : format ? format(value) : String(value)
  );
  const optionLabel = $derived(
    type === 'select' && !isEmpty
      ? options.find((o) => String(o.value) === String(value))?.label ?? String(value)
      : display
  );

  function toStr(v) {
    return v === null || v === undefined ? '' : String(v);
  }

  function start() {
    if (readOnly || saving) return;
    let d = toStr(value);
    if (type === 'date' && d.length > 10) d = d.slice(0, 10);
    draft = d;
    editing = true;
    queueMicrotask(() => {
      inputEl?.focus?.();
      if (inputEl && typeof inputEl.select === 'function' && type !== 'select') inputEl.select();
    });
  }

  function cancel() {
    editing = false;
  }

  async function commit() {
    if (!editing || saving) return;
    const cur = type === 'date' ? toStr(value).slice(0, 10) : toStr(value);
    if (toStr(draft) === cur) {
      editing = false;
      return;
    }
    /** @type {any} */
    let next = draft;
    if (type === 'number') next = draft === '' ? null : Number(draft);
    if (transform) next = transform(next);

    saving = true;
    try {
      // Save through the page's `updateField` server action so the write uses
      // the cookie JWT + org context (client localStorage token lacks org).
      const fd = new FormData();
      fd.append('field', field);
      fd.append('value', JSON.stringify(next ?? null));
      const res = await fetch('?/updateField', { method: 'POST', body: fd });
      /** @type {any} */
      const result = deserialize(await res.text());
      if (result.type === 'failure') throw new Error(result.data?.error || 'Save failed');
      if (result.type === 'error') throw new Error(result.error?.message || 'Save failed');
      editing = false;
      toast.success('Saved');
      onsaved?.();
      await invalidateAll();
    } catch (err) {
      toast.error(/** @type {any} */ (err)?.message || 'Failed to save');
      // Stay in edit mode so the user can retry or press Esc to revert.
    } finally {
      saving = false;
    }
  }

  /** @param {KeyboardEvent} e */
  function onkeydown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      cancel();
    } else if (e.key === 'Enter') {
      if (type === 'textarea' || type === 'markdown') {
        if (e.ctrlKey || e.metaKey) {
          e.preventDefault();
          commit();
        }
      } else {
        e.preventDefault();
        commit();
      }
    }
  }

  const inputClass =
    'w-full rounded-md border border-[color:var(--border-strong,var(--border))] bg-[color:var(--bg)] px-2 py-1 text-[13px] text-[color:var(--text)] outline-none focus:border-[color:var(--color-primary-default,#2563eb)]';
</script>

<div class={cn('group/ef relative', className)}>
  {#if editing}
    {#if type === 'select'}
      <select bind:this={inputEl} bind:value={draft} onblur={commit} onkeydown={onkeydown} class={inputClass} disabled={saving}>
        <option value="">{placeholder || '—'}</option>
        {#each options as opt (opt.value)}
          <option value={String(opt.value)}>{opt.label}</option>
        {/each}
      </select>
    {:else if type === 'textarea' || type === 'markdown'}
      <textarea
        bind:this={inputEl}
        bind:value={draft}
        onblur={commit}
        onkeydown={onkeydown}
        rows={type === 'markdown' ? 8 : 3}
        placeholder={placeholder || (type === 'markdown' ? '# Heading\n**bold**, - bullets, [link](https://…)' : '')}
        class={cn(inputClass, 'resize-y font-mono leading-[1.6]')}
        disabled={saving}
      ></textarea>
      {#if type === 'markdown'}
        <p class="mt-1 text-[11px] text-[color:var(--text-subtle)]">
          Markdown: <code># H1</code> · <code>## H2</code> · <code>**bold**</code> · <code>- list</code>. Ctrl/⌘+Enter to save.
        </p>
      {/if}
    {:else}
      <input
        bind:this={inputEl}
        type={type === 'number' ? 'number' : type === 'date' ? 'date' : type === 'email' ? 'email' : type === 'tel' ? 'tel' : type === 'url' ? 'url' : 'text'}
        bind:value={draft}
        onblur={commit}
        onkeydown={onkeydown}
        placeholder={placeholder}
        class={inputClass}
        disabled={saving}
      />
    {/if}
    {#if saving}
      <span class="pointer-events-none absolute right-2 top-1.5 text-[color:var(--text-subtle)]">
        <Loader2 class="h-3.5 w-3.5 animate-spin" />
      </span>
    {/if}
  {:else if type === 'markdown'}
    <button
      type="button"
      onclick={start}
      class={cn(
        'block w-full rounded-md px-2 py-1.5 text-left -mx-2',
        !readOnly && 'cursor-text hover:bg-[color:var(--bg-elevated)]',
        readOnly && 'cursor-default'
      )}
      disabled={readOnly}
    >
      <MarkdownView value={value} emptyText={emptyText} />
    </button>
  {:else}
    <button
      type="button"
      onclick={start}
      title={readOnly ? '' : 'Click to edit'}
      class={cn(
        'group/ef-btn flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[13px] -mx-2',
        !readOnly && 'cursor-text hover:bg-[color:var(--bg-elevated)]',
        readOnly && 'cursor-default'
      )}
      disabled={readOnly}
    >
      {#if isEmpty}
        <span class="text-[color:var(--text-subtle)]">{readOnly ? emptyText : placeholder || emptyText}</span>
      {:else}
        <span class="min-w-0 truncate text-[color:var(--text)]">{optionLabel}</span>
      {/if}
      {#if !readOnly}
        <Pencil class="h-3 w-3 shrink-0 text-[color:var(--text-subtle)] opacity-0 transition-opacity group-hover/ef-btn:opacity-100" />
      {/if}
    </button>
  {/if}
</div>
