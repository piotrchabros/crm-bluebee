<script>
  import { ExternalLink } from '@lucide/svelte';

  /**
   * Display a related-record value with a control to open that record's detail
   * page in a new browser tab.
   * @type {{ value?: string, href?: string, label?: string, emptyText?: string, class?: string }}
   */
  let {
    value = '',
    href = '',
    label = 'record',
    emptyText = '—',
    class: className = ''
  } = $props();
</script>

{#if value}
  <span class="inline-flex items-center gap-1.5 {className}">
    <span class="truncate text-[color:var(--text)]">{value}</span>
    {#if href}
      <a
        {href}
        target="_blank"
        rel="noopener noreferrer"
        title={`Open ${label} in a new tab`}
        aria-label={`Open ${label} in a new tab`}
        class="inline-flex shrink-0 items-center text-[color:var(--text-subtle)] transition-colors hover:text-[color:var(--text)]"
      >
        <ExternalLink class="h-3.5 w-3.5" />
      </a>
    {/if}
  </span>
{:else}
  <span class="text-[color:var(--text-subtle)] {className}">{emptyText}</span>
{/if}
