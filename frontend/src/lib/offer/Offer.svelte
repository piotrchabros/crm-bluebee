<script>
  // Full offer renderer, ported from bluebee-website DataOffer.tsx + leaf
  // components. Renders the public offer payload into themed HTML; offer.css
  // (imported by the page) provides all .offer-* styling and [data-brand] themes.
  import RichText from '$lib/offer/RichText.svelte';
  import { fixOrphans } from '$lib/offer/richtext.js';

  /** @type {{ offer: { client_name?: string, title?: string, offer_data?: any, branding?: any } }} */
  let { offer } = $props();

  const data = $derived(offer?.offer_data || {});
  const hero = $derived(data?.hero || {});
  const sections = $derived(data?.sections || []);

  // Per-org branding (Feature 5): theme + accent + logo/name come from the org.
  const branding = $derived(offer?.branding || {});
  const theme = $derived(branding.theme === 'light' ? 'light' : 'dark');
  const companyName = $derived(branding.company_name || '');
  const logoUrl = $derived(branding.logo_url || '');

  // Turn the org's accent hex into the three CSS vars offer.css expects,
  // overriding the per-theme defaults inline so any accent color works.
  function hexToRgba(hex, alpha) {
    const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim());
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }
  const accentVars = $derived.by(() => {
    const a = branding.accent;
    if (!a) return '';
    const soft = hexToRgba(a, 0.12);
    const border = hexToRgba(a, 0.35);
    let s = `--offer-accent: ${a};`;
    if (soft) s += ` --offer-accent-soft: ${soft};`;
    if (border) s += ` --offer-accent-border: ${border};`;
    return s;
  });

  function fmtPLN(v) {
    try {
      return new Intl.NumberFormat('pl-PL').format(v);
    } catch {
      return String(v);
    }
  }
</script>

<div class="offer-root" data-theme={theme} style={accentVars}>
  <header class="offer-topbar offer-no-print">
    <div class="offer-topbar-inner">
      <div class="offer-topbar-brand">
        {#if logoUrl}
          <img src={logoUrl} alt={companyName} style="max-height:28px;width:auto;" />
        {:else}
          <strong>{companyName}</strong>
        {/if}
      </div>
      <div class="offer-topbar-meta">
        <span>Dla<strong>{offer?.client_name || ''}</strong></span>
      </div>
    </div>
  </header>

  <main class="offer-main">
    <!-- Hero -->
    <section class="offer-hero">
      {#if hero.eyebrow}<span class="offer-hero-eyebrow">{hero.eyebrow}</span>{/if}
      <h1 class="offer-hero-title">{hero.titleLead} <em>{hero.titleEm}</em></h1>
      {#if hero.subtitle}<p class="offer-hero-subtitle"><RichText text={hero.subtitle} /></p>{/if}
      {#if hero.meta?.length}
        <div class="offer-hero-meta" style="grid-template-columns: repeat(4, minmax(0, 1fr)); max-width: none;">
          {#each hero.meta as m}
            <div class="offer-hero-meta-item">
              <span class="label">{m.label}</span>
              <span class="value">{m.value}</span>
            </div>
          {/each}
        </div>
      {/if}
    </section>

    <!-- Sections -->
    {#each sections as block}
      <section class="offer-section">
        <div class="offer-section-eyebrow">
          {#if block.number}<span class="offer-section-number">{block.number}</span>{/if}
          <span class="offer-section-line"></span>
        </div>
        <h2 class="offer-section-title">{fixOrphans(block.title)}</h2>
        {#if block.intro}<div class="offer-section-intro"><RichText text={block.intro} /></div>{/if}
        {@render body(block)}
      </section>
    {/each}
  </main>
</div>

{#snippet highlightBox(h)}
  <div style="margin-top:28px;padding:22px 26px;background:var(--offer-accent-soft);border:1px solid var(--offer-accent-border);border-radius:14px;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.12em;font-weight:700;color:var(--offer-accent);">{h.label}</div>
    <div style="font-size:24px;font-weight:800;margin-top:4px;">{h.value}</div>
    {#if h.note}<p style="margin:10px 0 0;font-size:13.5px;line-height:1.6;color:var(--offer-text-muted);"><RichText text={h.note} /></p>{/if}
  </div>
{/snippet}

{#snippet body(block)}
  {#if block.type === 'prose'}
    {#each block.paragraphs as p}<p><RichText text={p} /></p>{/each}

  {:else if block.type === 'checklist'}
    <div class="offer-checklist">
      {#if block.listTitle}<div class="offer-checklist-title">{block.listTitle}</div>{/if}
      <ul>{#each block.items as it}<li><span><RichText text={it} /></span></li>{/each}</ul>
    </div>
    {#if block.highlight}{@render highlightBox(block.highlight)}{/if}

  {:else if block.type === 'stats'}
    {#if block.stats?.length}
      <div style="display:grid;gap:16px;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));">
        {#each block.stats as s}
          <div style="padding:22px 24px;background:var(--offer-bg-card);border:1px solid var(--offer-border);border-radius:14px;">
            <div style="font-size:28px;font-weight:800;color:var(--offer-accent);letter-spacing:-0.02em;">{s.value}</div>
            <div style="font-size:13.5px;color:var(--offer-text-muted);margin-top:4px;">{s.label}</div>
          </div>
        {/each}
      </div>
    {/if}
    {#each block.chips || [] as c}
      <div style="margin-top:28px;">
        {#if c.label}<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.12em;font-weight:700;color:var(--offer-accent);margin-bottom:12px;">{c.label}</div>{/if}
        <div style="display:flex;flex-wrap:wrap;gap:10px;">
          {#each c.items as item}<span style="font-size:14px;font-weight:600;padding:8px 16px;border-radius:999px;background:var(--offer-accent-soft);border:1px solid var(--offer-accent-border);color:var(--offer-text);">{item}</span>{/each}
        </div>
      </div>
    {/each}
    {#if block.highlight}{@render highlightBox(block.highlight)}{/if}

  {:else if block.type === 'techGrid'}
    <div style="display:grid;gap:16px;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));margin-top:8px;">
      {#each block.items as it}
        <div style="padding:20px 22px;background:var(--offer-bg-card);border:1px solid var(--offer-border);border-radius:14px;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.12em;font-weight:700;color:var(--offer-accent);margin-bottom:8px;">{it.label}</div>
          <div style="font-size:15px;line-height:1.55;color:var(--offer-text);"><RichText text={it.value} /></div>
        </div>
      {/each}
    </div>
    {#if block.note}<p style="margin-top:24px;max-width:880px;font-size:14.5px;color:var(--offer-text-muted);"><RichText text={block.note} /></p>{/if}

  {:else if block.type === 'valueGrid'}
    {#if block.lead}<p style="max-width:880px;"><RichText text={block.lead} /></p>{/if}
    <div style="display:grid;gap:18px;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));">
      {#each block.items as it}
        <div style="padding:26px 26px;background:var(--offer-bg-card);border:1px solid var(--offer-border);border-radius:16px;">
          <h4 style="margin:0 0 10px;font-size:18px;letter-spacing:-0.01em;">{fixOrphans(it.title)}</h4>
          <p style="margin:0;font-size:14.5px;line-height:1.65;"><RichText text={it.body} /></p>
        </div>
      {/each}
    </div>
    {#if block.highlight}{@render highlightBox(block.highlight)}{/if}

  {:else if block.type === 'highlight'}
    {@render highlightBox({ label: block.label, value: block.value, note: block.note })}

  {:else if block.type === 'warmNote'}
    <div style="margin-top:28px;padding:20px 24px;background:rgba(255,116,37,0.07);border:1px solid rgba(255,116,37,0.28);border-radius:14px;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.12em;font-weight:700;color:var(--offer-warm);margin-bottom:8px;">{block.noteTitle}</div>
      <p style="margin:0;font-size:14.5px;line-height:1.65;color:var(--offer-text-muted);"><RichText text={block.body} /></p>
    </div>

  {:else if block.type === 'table'}
    {@render offerTable(block.headers, block.rows)}

  {:else if block.type === 'pricing'}
    {@render pricing(block.expanded)}

  {:else if block.type === 'cta'}
    <div class="offer-cta">
      <h3>{fixOrphans(block.ctaTitle)}</h3>
      <p><RichText text={block.description} /></p>
      {#if block.actions?.length}
        <div class="offer-cta-actions">
          {#each block.actions as a}<a href={a.href} class={`offer-btn${a.ghost ? ' offer-btn-ghost' : ''}`}>{a.label}</a>{/each}
        </div>
      {/if}
    </div>
  {/if}
{/snippet}

{#snippet offerTable(headers, rows)}
  <div class="offer-table-wrap">
    <table class="offer-table">
      {#if headers?.length}
        <thead><tr>{#each headers as h}<th>{h}</th>{/each}</tr></thead>
      {/if}
      <tbody>
        {#each rows as row}
          <tr class={row.isTotal ? 'is-total' : undefined}>
            {#each row.cells as cell}<td><RichText text={cell} /></td>{/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/snippet}

{#snippet pricingCard(card)}
  {@const vat = Math.round((card.netPrice || 0) * 0.23)}
  {@const gross = (card.netPrice || 0) + vat}
  <div class={`offer-pricing-card${card.recommended ? ' is-recommended' : ''}`}>
    <div class="offer-pricing-variant">{card.variant}</div>
    <div class="offer-pricing-title">{card.title}</div>
    <div class="offer-pricing-amount">
      <em>{fmtPLN(card.netPrice)}</em> PLN{#if card.period}<span class="offer-pricing-period">{card.period}</span>{/if}
    </div>
    <div class="offer-pricing-currency">{card.subLabel}</div>
    <div class="offer-pricing-breakdown">
      <div class="offer-pricing-breakdown-row"><span>Kwota netto</span><span>{fmtPLN(card.netPrice)} PLN</span></div>
      <div class="offer-pricing-breakdown-row"><span>VAT (23%)</span><span>{fmtPLN(vat)} PLN</span></div>
      <div class="offer-pricing-breakdown-row is-total"><span>Łącznie brutto</span><span class="amount">{fmtPLN(gross)} PLN</span></div>
    </div>
    {#if card.footer}<div style="margin-top:20px;font-size:13px;color:var(--offer-text-subtle);line-height:1.6;"><RichText text={card.footer} /></div>{/if}
  </div>
{/snippet}

{#snippet pricing(ex)}
  {#if ex}
    <div class="offer-comparison">
      {#each ex.comparison.variants as v}
        <article class={`offer-comparison-card${v.recommended ? ' is-recommended' : ''}`}>
          {#if v.recommended && v.badge}<span class="offer-comparison-badge">{v.badge}</span>{/if}
          <h3 class="offer-comparison-title">{v.title}</h3>
          {#if v.subtitle}<div class="offer-comparison-subtitle">{v.subtitle}</div>{/if}
          <div class="offer-comparison-desc"><RichText text={v.description} /></div>
          <ul class="offer-comparison-benefits">
            {#each v.benefits as b}<li><span><strong>{b.label}:</strong> <RichText text={b.value} /></span></li>{/each}
          </ul>
          {#if v.recommendation}<div class="offer-comparison-rec"><RichText text={v.recommendation} /></div>{/if}
        </article>
      {/each}
    </div>

    <div style="margin-top:44px;">
      <h3 style="font-size:20px;margin-bottom:20px;text-transform:uppercase;letter-spacing:0.08em;color:var(--offer-accent);">{fixOrphans(ex.table.title)}</h3>
      {@render offerTable(ex.table.headers, ex.table.rows)}
    </div>

    <div class="offer-pricing-grid" style="margin-top:44px;">
      {#each ex.cards as c}{@render pricingCard(c)}{/each}
    </div>

    {#if ex.note}<p style="margin-top:20px;font-size:13.5px;color:var(--offer-text-subtle);max-width:880px;"><RichText text={ex.note} /></p>{/if}
  {/if}
{/snippet}
