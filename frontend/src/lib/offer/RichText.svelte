<script>
  // Renders a rich string (**bold** + [links]) as safe Svelte markup — no {@html}.
  import { parseInline } from '$lib/offer/richtext.js';

  /** @type {{ text?: string }} */
  let { text = '' } = $props();
  const tokens = $derived(parseInline(text));
</script>

{#each tokens as t}{#if t.type === 'bold'}<strong>{t.value}</strong>{:else if t.type === 'link'}<a
      href={t.href}
      target={t.external ? '_blank' : undefined}
      rel={t.external ? 'noopener noreferrer' : undefined}>{t.value}</a
    >{:else}{t.value}{/if}{/each}
