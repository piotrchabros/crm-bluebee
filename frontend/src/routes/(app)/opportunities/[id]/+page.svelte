<script>
  import { goto } from '$app/navigation';
  import {
    Pencil,
    Mail,
    Phone,
    MoreHorizontal,
    Paperclip,
    MessageSquare,
    Calendar
  } from '@lucide/svelte';
  import { PageHeader } from '$lib/components/layout';
  import { StageStepper } from '$lib/components/ui/stage-stepper';
  import { Timeline, TimelineItem } from '$lib/components/ui/timeline';
  import { SectionCard } from '$lib/components/ui/section-card/index.js';
  import CustomFieldsPanel from '$lib/components/custom-fields/CustomFieldsPanel.svelte';
  import AttachmentPanel from '$lib/components/attachments/AttachmentPanel.svelte';
  import * as Tabs from '$lib/components/ui/tabs/index.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import { formatCurrency, formatDate, formatRelativeDate, getNameInitials } from '$lib/utils/formatting.js';
  import {
    OPPORTUNITY_STAGES,
    OPPORTUNITY_TYPES,
    OPPORTUNITY_SOURCES,
    CURRENCY_CODES
  } from '$lib/constants/filters.js';
  import { opportunities as opportunitiesApi } from '$lib/api.js';
  import { EditableField } from '$lib/components/ui/editable-field';
  import { RelationLink } from '$lib/components/ui/relation-link';

  /** @type {{ data: { opportunity: any, comments: any[], attachments: any[], contacts: any[], users: any[], commentPermission: boolean, customFieldDefinitions: any[], customFieldValues: Record<string, any> } }} */
  let { data } = $props();

  const opp = $derived(data.opportunity || {});
  const comments = $derived(data.comments || []);
  const attachments = $derived(data.attachments || []);
  const contacts = $derived(data.contacts || []);
  const customFieldDefinitions = $derived(data.customFieldDefinitions || []);
  const customFieldValues = $derived(data.customFieldValues || {});

  let tab = $state('overview');

  // --- Inline-edit support (record detail page) ---
  const recordId = $derived(opp?.id);

  // Option values are the exact backend choice keys so PATCH sends what the
  // serializer accepts (see backend/common/utils.py: STAGES, OPPORTUNITY_TYPES,
  // SOURCES, CURRENCY_CODES). Drop the 'ALL'/'' filter sentinels.
  const stageOptions = OPPORTUNITY_STAGES.filter((s) => s.value && s.value !== 'ALL').map((s) => ({
    value: s.value,
    label: s.label
  }));
  const typeOptions = OPPORTUNITY_TYPES.filter((t) => t.value).map((t) => ({
    value: t.value,
    label: t.label
  }));
  const sourceOptions = OPPORTUNITY_SOURCES.filter((s) => s.value).map((s) => ({
    value: s.value,
    label: s.label
  }));
  const currencyOptions = CURRENCY_CODES.filter((c) => c.value).map((c) => ({
    value: c.value,
    label: c.label
  }));

  // Build the 6 stepper cells from OPPORTUNITY_STAGES (skipping the 'ALL' filter sentinel)
  const stepperStages = $derived(
    OPPORTUNITY_STAGES.filter((s) => s.value !== 'ALL').map((s) => ({
      value: s.value,
      label: s.label
    }))
  );

  // Relations
  const accountId = $derived(opp?.account?.id);
  const accountName = $derived(opp?.account?.name || '');

  /** @typedef {{ id: string, name: string }} ContactLink */
  /** @type {ContactLink[]} */
  const contactLinks = $derived(
    Array.isArray(contacts)
      ? contacts.map((/** @type {any} */ ct) => ({
          id: ct?.id,
          name: `${ct?.first_name || ''} ${ct?.last_name || ''}`.trim() || ct?.email || 'Contact'
        }))
      : []
  );

  const fmtMoney = (/** @type {any} */ v) =>
    v != null && v !== '' ? formatCurrency(v, opp?.currency || 'USD') : '';
  const fmtPct = (/** @type {any} */ v) => (v != null && v !== '' ? `${v}%` : '');
  const fmtDate = (/** @type {any} */ v) => (v ? formatDate(v) : '');

  // Timeline items: comments + attachments + created event, sorted DESC by timestamp.
  const timelineItems = $derived.by(() => {
    /** @type {Array<{ id: string, ts: string, kind: 'comment' | 'attachment' | 'created', payload: any }>} */
    const items = [];
    for (const c of comments) {
      items.push({ id: `comment-${c.id}`, ts: c.commented_on || c.commented_on_arrow || '', kind: 'comment', payload: c });
    }
    for (const a of attachments) {
      items.push({ id: `attachment-${a.id}`, ts: a.created_on || a.created_at || '', kind: 'attachment', payload: a });
    }
    if (opp?.created_at || opp?.created_on) {
      items.push({ id: `created-${opp.id}`, ts: opp.created_at || opp.created_on, kind: 'created', payload: opp });
    }
    return items.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());
  });
</script>

<svelte:head>
  <title>{opp?.name || 'Opportunity'} · BottleCRM</title>
</svelte:head>

<PageHeader
  title={opp?.name || 'Opportunity'}
  breadcrumb={[
    { label: 'Opportunities', href: '/opportunities' },
    { label: opp?.name || '—' }
  ]}
>
  {#snippet meta()}
    <div class="flex flex-wrap items-center gap-3 text-[12px] leading-none text-[color:var(--text-subtle)]">
      {#if opp?.created_at || opp?.created_on}
        <span>Created {formatRelativeDate(opp.created_at || opp.created_on)}</span>
      {/if}
      {#if opp?.account?.name}
        <span>·</span>
        <a href={`/accounts`} class="hover:text-[color:var(--text-muted)]">{opp.account.name}</a>
      {/if}
      {#if opp?.assigned_to?.[0]}
        <span>·</span>
        <span class="flex items-center gap-1.5">
          <span class="flex size-4 items-center justify-center rounded-full bg-[color:var(--bg-elevated)] text-[9px] font-medium text-[color:var(--text-muted)]">
            {getNameInitials(opp.assigned_to[0].user_details?.email || '?', '')}
          </span>
          {opp.assigned_to[0].user_details?.email || 'Unassigned'}
        </span>
      {/if}
    </div>
  {/snippet}

  {#snippet amount()}
    {#if opp?.amount != null}
      <span class="text-[28px] font-bold leading-none tabular-nums text-[color:var(--text)]">
        {formatCurrency(opp.amount, opp.currency || 'USD')}
      </span>
      {#if opp?.probability != null}
        <span class="text-[11px] leading-none text-[color:var(--text-subtle)]">
          {opp.probability}% probability
        </span>
      {/if}
    {/if}
  {/snippet}

  {#snippet actions()}
    <div class="flex items-center gap-1.5">
      <Button variant="ghost" size="icon" aria-label="Email"><Mail class="size-4" /></Button>
      <Button variant="ghost" size="icon" aria-label="Call"><Phone class="size-4" /></Button>
      <Button variant="ghost" size="icon" aria-label="More"><MoreHorizontal class="size-4" /></Button>
      <Button variant="outline" size="sm" onclick={() => opp?.id && goto(`/opportunities/${opp.id}/edit`)}>
        <Pencil class="mr-1.5 size-3.5" /> Edit
      </Button>
    </div>
  {/snippet}
</PageHeader>

<!-- Stage stepper -->
<div class="px-7 pb-3 md:px-8">
  <StageStepper stages={stepperStages} current={opp?.stage || ''} />
</div>

<!-- Tabs -->
<Tabs.Root bind:value={tab} class="px-7 md:px-8">
  <Tabs.List class="">
    <Tabs.Trigger class="" value="overview">Overview</Tabs.Trigger>
    <Tabs.Trigger class="" value="activity">
      Activity
      <span class="ml-1.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[color:var(--bg-elevated)] px-1 text-[10px] tabular-nums text-[color:var(--text-subtle)]">
        {timelineItems.length}
      </span>
    </Tabs.Trigger>
    <Tabs.Trigger class="" value="files">
      Files
      <span class="ml-1.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[color:var(--bg-elevated)] px-1 text-[10px] tabular-nums text-[color:var(--text-subtle)]">
        {attachments.length}
      </span>
    </Tabs.Trigger>
  </Tabs.List>

  <Tabs.Content class="" value="overview">
    {#snippet efRow(label, props)}
      <div class="grid grid-cols-[120px_minmax(0,1fr)] items-center gap-3 py-0.5">
        <span class="text-[12px] text-[color:var(--text-subtle)]">{label}</span>
        <EditableField {recordId} api={opportunitiesApi} {...props} />
      </div>
    {/snippet}

    <div class="grid grid-cols-1 gap-6 pt-4 pb-8 lg:grid-cols-[1fr_320px]">
      <!-- Main column -->
      <div class="flex flex-col gap-6">
        <!-- Notes (Markdown) -->
        <SectionCard title="Notes">
          <EditableField
            type="markdown"
            field="description"
            value={opp?.description}
            {recordId}
            api={opportunitiesApi}
            emptyText="Click to add notes — Markdown supported (# H1, ## H2, **bold**, - lists)."
          />
        </SectionCard>

        {#if customFieldDefinitions.length > 0}
          <CustomFieldsPanel
            target="Opportunity"
            definitions={customFieldDefinitions}
            values={customFieldValues}
            title="Custom Fields"
          />
        {/if}

        <!-- Deal -->
        <SectionCard title="Deal">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Name', { field: 'name', value: opp?.name, placeholder: 'Add name' })}
            {@render efRow('Stage', { type: 'select', field: 'stage', value: opp?.stage, options: stageOptions, placeholder: '—' })}
            {@render efRow('Type', { type: 'select', field: 'opportunity_type', value: opp?.opportunity_type, options: typeOptions, placeholder: '—' })}
            {@render efRow('Amount', { type: 'number', field: 'amount', value: opp?.amount, placeholder: '0', format: fmtMoney })}
            {@render efRow('Currency', { type: 'select', field: 'currency', value: opp?.currency, options: currencyOptions, placeholder: '—' })}
            {@render efRow('Probability', { type: 'number', field: 'probability', value: opp?.probability, placeholder: '0', format: fmtPct })}
            {@render efRow('Close date', { type: 'date', field: 'closed_on', value: opp?.closed_on, format: fmtDate })}
            {@render efRow('Lead source', { type: 'select', field: 'lead_source', value: opp?.lead_source, options: sourceOptions, placeholder: '—' })}
          </div>
        </SectionCard>

        <!-- Activity timeline card -->
        <SectionCard title="Activity" class="px-4 py-2">
            <Timeline isEmpty={timelineItems.length === 0}>
              {#each timelineItems as item (item.id)}
                {#if item.kind === 'comment'}
                  <TimelineItem
                    variant="violet"
                    time={item.ts ? formatRelativeDate(item.ts) : ''}
                    quote={item.payload.comment || ''}
                  >
                    {#snippet icon()}<MessageSquare class="size-3.5" />{/snippet}
                    {#snippet text()}
                      <strong>{item.payload.commented_by_user || 'Someone'}</strong> commented
                    {/snippet}
                  </TimelineItem>
                {:else if item.kind === 'attachment'}
                  <TimelineItem
                    time={item.ts ? formatRelativeDate(item.ts) : ''}
                  >
                    {#snippet icon()}<Paperclip class="size-3.5" />{/snippet}
                    {#snippet text()}
                      <strong>{item.payload.created_by_user || 'Someone'}</strong> uploaded
                      <strong>{item.payload.file_name || 'a file'}</strong>
                    {/snippet}
                  </TimelineItem>
                {:else}
                  <TimelineItem
                    variant="success"
                    time={item.ts ? formatRelativeDate(item.ts) : ''}
                  >
                    {#snippet icon()}<Calendar class="size-3.5" />{/snippet}
                    {#snippet text()}
                      Opportunity created
                    {/snippet}
                  </TimelineItem>
                {/if}
              {/each}
            </Timeline>
          </SectionCard>
      </div>

      <!-- Right rail -->
      <div class="flex flex-col gap-6">
        <!-- Relations -->
        <SectionCard title="Related">
          <dl class="grid grid-cols-1 gap-y-3 text-[12px]">
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Account</dt>
              <dd class="min-w-0 text-right">
                <RelationLink
                  value={accountName}
                  href={accountId ? `/accounts/${accountId}` : ''}
                  label="account"
                />
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-3">
              <dt class="shrink-0 text-[color:var(--text-subtle)]">Contacts</dt>
              <dd class="flex min-w-0 flex-col items-end gap-1">
                {#if contactLinks.length === 0}
                  <span class="text-[color:var(--text-subtle)]">—</span>
                {:else}
                  {#each contactLinks as ct (ct.id)}
                    <RelationLink
                      value={ct.name}
                      href={ct.id ? `/contacts/${ct.id}` : ''}
                      label="contact"
                    />
                  {/each}
                {/if}
              </dd>
            </div>
          </dl>
        </SectionCard>

        <!-- Record meta (read-only) -->
        <SectionCard title="Record">
          <dl class="grid grid-cols-1 gap-y-2.5 text-[12px]">
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Created</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {opp?.created_at || opp?.created_on
                  ? formatDate(opp.created_at || opp.created_on)
                  : '—'}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Updated</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {opp?.updated_at ? formatRelativeDate(opp.updated_at) : '—'}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Created by</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {opp?.created_by?.email || '—'}
              </dd>
            </div>
          </dl>
        </SectionCard>

        <SectionCard title="Tags">
            {#if (opp?.tags || []).length === 0}
              <p class="text-[12px] italic text-[color:var(--text-subtle)]">No tags.</p>
            {:else}
              <div class="flex flex-wrap gap-1.5">
                {#each opp.tags as tag, i (tag.id ?? tag.slug ?? tag.name ?? i)}
                  <Badge variant="secondary" class="bg-[color:var(--bg-elevated)] text-[color:var(--text-muted)]">
                    {tag.name}
                  </Badge>
                {/each}
              </div>
            {/if}
          </SectionCard>
      </div>
    </div>
  </Tabs.Content>

  <Tabs.Content class="" value="activity">
    <div class="pt-4 pb-8">
      <SectionCard title="All activity" class="px-4 py-2">
          <Timeline isEmpty={timelineItems.length === 0}>
            {#each timelineItems as item (item.id)}
              {#if item.kind === 'comment'}
                <TimelineItem variant="violet" time={item.ts ? formatRelativeDate(item.ts) : ''} quote={item.payload.comment || ''}>
                  {#snippet icon()}<MessageSquare class="size-3.5" />{/snippet}
                  {#snippet text()}<strong>{item.payload.commented_by_user || 'Someone'}</strong> commented{/snippet}
                </TimelineItem>
              {:else if item.kind === 'attachment'}
                <TimelineItem time={item.ts ? formatRelativeDate(item.ts) : ''}>
                  {#snippet icon()}<Paperclip class="size-3.5" />{/snippet}
                  {#snippet text()}<strong>{item.payload.created_by_user || 'Someone'}</strong> uploaded <strong>{item.payload.file_name || 'a file'}</strong>{/snippet}
                </TimelineItem>
              {:else}
                <TimelineItem variant="success" time={item.ts ? formatRelativeDate(item.ts) : ''}>
                  {#snippet icon()}<Calendar class="size-3.5" />{/snippet}
                  {#snippet text()}Opportunity created{/snippet}
                </TimelineItem>
              {/if}
            {/each}
          </Timeline>
        </SectionCard>
    </div>
  </Tabs.Content>

  <Tabs.Content class="" value="files">
    <div class="pt-4 pb-8">
      <SectionCard title="Files">
        <AttachmentPanel entity="opportunities" recordId={opp.id} {attachments} />
      </SectionCard>
    </div>
  </Tabs.Content>
</Tabs.Root>
