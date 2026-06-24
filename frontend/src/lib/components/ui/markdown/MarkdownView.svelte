<script>
  import { renderMarkdown } from '$lib/utils/markdown.js';

  /** @type {{ value?: string, class?: string, emptyText?: string }} */
  let { value = '', class: className = '', emptyText = 'No notes' } = $props();

  const html = $derived(renderMarkdown(value || ''));
</script>

{#if value && value.trim()}
  <!-- Safe: renderMarkdown() escapes all input before emitting a fixed tag allowlist. -->
  <div class="crm-md {className}">{@html html}</div>
{:else}
  <span class="text-[13px] italic text-[color:var(--text-subtle)]">{emptyText}</span>
{/if}

<style>
  .crm-md :global(h1) {
    font-size: 1.125rem;
    font-weight: 600;
    line-height: 1.4;
    margin: 0.6em 0 0.3em;
    color: var(--text);
  }
  .crm-md :global(h2) {
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.4;
    margin: 0.5em 0 0.25em;
    color: var(--text);
  }
  .crm-md :global(p) {
    font-size: 0.8125rem;
    line-height: 1.6;
    margin: 0 0 0.5em;
    color: var(--text-muted);
  }
  .crm-md :global(ul),
  .crm-md :global(ol) {
    font-size: 0.8125rem;
    line-height: 1.6;
    margin: 0 0 0.5em;
    padding-left: 1.25em;
    color: var(--text-muted);
  }
  .crm-md :global(ul) {
    list-style: disc;
  }
  .crm-md :global(ol) {
    list-style: decimal;
  }
  .crm-md :global(li) {
    margin: 0.1em 0;
  }
  .crm-md :global(strong) {
    font-weight: 600;
    color: var(--text);
  }
  .crm-md :global(a) {
    color: var(--color-primary-default, #2563eb);
    text-decoration: underline;
  }
  .crm-md :global(:first-child) {
    margin-top: 0;
  }
  .crm-md :global(:last-child) {
    margin-bottom: 0;
  }
</style>
