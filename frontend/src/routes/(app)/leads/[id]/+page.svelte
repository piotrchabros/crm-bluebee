<script>
  import { goto } from '$app/navigation';
  import {
    Pencil,
    Mail,
    Phone,
    MoreHorizontal,
    Paperclip,
    MessageSquare,
    Calendar,
    ArrowRightCircle,
    Globe,
    Briefcase,
    Building2,
    DollarSign,
    Target,
    Star,
    MapPin,
    Users,
    UserCheck,
    FileText,
    ExternalLink
  } from '@lucide/svelte';
  import { LinkedinIcon as Linkedin } from '$lib/components/icons';
  import { PageHeader } from '$lib/components/layout';
  import { StageStepper } from '$lib/components/ui/stage-stepper';
  import { Timeline, TimelineItem } from '$lib/components/ui/timeline';
  import { SectionCard } from '$lib/components/ui/section-card/index.js';
  import * as Tabs from '$lib/components/ui/tabs/index.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import CustomFieldsPanel from '$lib/components/custom-fields/CustomFieldsPanel.svelte';
  import AttachmentPanel from '$lib/components/attachments/AttachmentPanel.svelte';
  import {
    formatRelativeDate,
    formatDate,
    formatCurrency,
    getNameInitials
  } from '$lib/utils/formatting.js';
  import {
    leadStatusOptions,
    leadRatingOptions,
    getOptionLabel,
    getOptionStyle
  } from '$lib/utils/table-helpers.js';
  import { INDUSTRIES, COUNTRIES } from '$lib/constants/lead-choices.js';
  import { CURRENCY_CODES } from '$lib/constants/filters.js';
  import { leads as leadsApi } from '$lib/api.js';
  import { EditableField } from '$lib/components/ui/editable-field';
  import { getCountryName } from '$lib/constants/countries.js';

  /** @type {{ data: { lead: any, comments: any[], attachments: any[], tags: any[], users: any[], commentPermission: boolean, customFieldDefinitions: any[], customFieldValues: Record<string, unknown> } }} */
  let { data } = $props();

  const lead = $derived(data.lead || {});
  const comments = $derived(data.comments || []);
  const attachments = $derived(data.attachments || []);
  const tags = $derived(data.tags || []);
  const customFieldDefinitions = $derived(data.customFieldDefinitions || []);
  const customFieldValues = $derived(data.customFieldValues || {});

  let tab = $state('overview');

  // Normalize backend status ("in process", "assigned") to leadStatusOptions value format ("IN_PROCESS")
  const normalizedStatus = $derived(
    (lead?.status || '').toString().toUpperCase().replace(/\s+/g, '_')
  );
  const normalizedRating = $derived((lead?.rating || '').toString().toUpperCase());

  const stepperStages = $derived(
    leadStatusOptions.map((s) => ({ value: s.value, label: s.label }))
  );

  const fullName = $derived(
    [lead?.salutation, lead?.first_name, lead?.last_name]
      .filter(Boolean)
      .join(' ')
      .trim() ||
      lead?.email ||
      'Lead'
  );

  const sourceLabel = $derived(
    lead?.source
      ? lead.source.replace(/\b\w/g, (/** @type {string} */ c) => c.toUpperCase())
      : ''
  );

  const industryLabel = $derived(
    INDUSTRIES.find((i) => i.value === lead?.industry)?.label || lead?.industry || ''
  );

  /** @typedef {{ id: string, email: string }} AssignedUser */
  /** @type {AssignedUser[]} */
  const assignedUsers = $derived(
    Array.isArray(lead?.assigned_to)
      ? lead.assigned_to
          .map((/** @type {any} */ p) => ({
            id: p?.id,
            email: p?.user_details?.email || p?.user?.email || ''
          }))
          .filter((/** @type {AssignedUser} */ u) => u.email)
      : []
  );

  /** @type {{ id: string, name: string }[]} */
  const teams = $derived(
    Array.isArray(lead?.teams)
      ? lead.teams.map((/** @type {any} */ t) => ({ id: t?.id, name: t?.name || '' }))
      : []
  );

  const probability = $derived(
    typeof lead?.probability === 'number' ? Math.max(0, Math.min(100, lead.probability)) : null
  );

  const hasDeal = $derived(
    lead?.opportunity_amount != null || probability !== null || !!lead?.close_date
  );

  const hasContactLinks = $derived(
    !!(lead?.email || lead?.phone || lead?.website || lead?.linkedin_url || lead?.job_title)
  );

  const hasAddress = $derived(
    !!(lead?.address_line || lead?.city || lead?.state || lead?.postcode || lead?.country)
  );

  const addressLines = $derived(
    [
      lead?.address_line,
      [lead?.city, lead?.state, lead?.postcode].filter(Boolean).join(', '),
      getCountryName(lead?.country)
    ].filter(Boolean)
  );

  function normalizeUrl(/** @type {string} */ raw) {
    if (!raw) return '';
    return /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  }

  // --- Inline-edit support (Feature 2: record detail pages) ---
  const recordId = $derived(lead?.id);

  // Option values are the exact backend choice keys so PATCH sends what the
  // serializer accepts (see backend/common/utils.py + leads/models.py).
  const salutationOptions = [
    { value: 'Mr', label: 'Mr' },
    { value: 'Mrs', label: 'Mrs' },
    { value: 'Ms', label: 'Ms' },
    { value: 'Dr', label: 'Dr' },
    { value: 'Prof', label: 'Prof' }
  ];
  const statusOptions = [
    { value: 'assigned', label: 'Assigned' },
    { value: 'in process', label: 'In Process' },
    { value: 'converted', label: 'Converted' },
    { value: 'recycled', label: 'Recycled' },
    { value: 'closed', label: 'Closed' }
  ];
  const ratingOptions = [
    { value: 'HOT', label: 'Hot' },
    { value: 'WARM', label: 'Warm' },
    { value: 'COLD', label: 'Cold' }
  ];
  const sourceOptions = [
    { value: 'call', label: 'Call' },
    { value: 'email', label: 'Email' },
    { value: 'existing customer', label: 'Existing Customer' },
    { value: 'partner', label: 'Partner' },
    { value: 'public relations', label: 'Public Relations' },
    { value: 'compaign', label: 'Campaign' },
    { value: 'other', label: 'Other' }
  ];
  const currencyOptions = CURRENCY_CODES.filter((c) => c.value).map((c) => ({
    value: c.value,
    label: c.label
  }));
  const industryOptions = INDUSTRIES.map((i) => ({ value: i.value, label: i.label }));
  const countryOptions = COUNTRIES.map((c) => ({ value: c.value, label: c.label }));

  const fmtMoney = (/** @type {any} */ v) =>
    v != null && v !== '' ? formatCurrency(v, lead?.currency || 'USD') : '';
  const fmtPct = (/** @type {any} */ v) => (v != null && v !== '' ? `${v}%` : '');
  const fmtDate = (/** @type {any} */ v) => (v ? formatDate(v) : '');

  // Timeline items: comments + attachments + created event, sorted DESC by timestamp.
  const timelineItems = $derived.by(() => {
    /** @type {Array<{ id: string, ts: string, kind: 'comment' | 'attachment' | 'created', payload: any }>} */
    const items = [];
    for (const c of comments) {
      items.push({ id: `comment-${c.id}`, ts: c.commented_on || '', kind: 'comment', payload: c });
    }
    for (const a of attachments) {
      items.push({
        id: `attachment-${a.id}`,
        ts: a.created_on || a.created_at || '',
        kind: 'attachment',
        payload: a
      });
    }
    if (lead?.created_at || lead?.created_on) {
      items.push({
        id: `created-${lead.id}`,
        ts: lead.created_at || lead.created_on,
        kind: 'created',
        payload: lead
      });
    }
    return items.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());
  });
</script>

<svelte:head>
  <title>{fullName} · BottleCRM</title>
</svelte:head>

<PageHeader
  title={fullName}
  subtitle={lead?.title || ''}
  breadcrumb={[{ label: 'Leads', href: '/leads' }, { label: fullName }]}
>
  {#snippet meta()}
    <div
      class="flex flex-wrap items-center gap-3 text-[12px] leading-none text-[color:var(--text-subtle)]"
    >
      {#if lead?.created_at || lead?.created_on}
        <span>Created {formatRelativeDate(lead.created_at || lead.created_on)}</span>
      {/if}
      {#if lead?.company_name}
        <span>·</span>
        <span class="flex items-center gap-1">
          <Building2 class="size-3" />
          {lead.company_name}
        </span>
      {/if}
      {#if assignedUsers.length > 0}
        <span>·</span>
        <span class="flex items-center gap-1.5">
          <span
            class="flex size-4 items-center justify-center rounded-full bg-[color:var(--bg-elevated)] text-[9px] font-medium text-[color:var(--text-muted)]"
          >
            {getNameInitials(assignedUsers[0].email, '')}
          </span>
          {assignedUsers[0].email}{#if assignedUsers.length > 1}
            <span class="text-[color:var(--text-subtle)]">+{assignedUsers.length - 1}</span>
          {/if}
        </span>
      {/if}
    </div>
  {/snippet}

  {#snippet actions()}
    <div class="flex items-center gap-1.5">
      {#if lead?.email}
        <Button variant="ghost" size="icon" aria-label="Email" href="mailto:{lead.email}">
          <Mail class="size-4" />
        </Button>
      {/if}
      {#if lead?.phone}
        <Button variant="ghost" size="icon" aria-label="Call" href="tel:{lead.phone}">
          <Phone class="size-4" />
        </Button>
      {/if}
      <Button variant="ghost" size="icon" aria-label="More"><MoreHorizontal class="size-4" /></Button>
      <Button
        variant="outline"
        size="sm"
        onclick={() => lead?.id && goto(`/leads/${lead.id}/edit`)}
      >
        <Pencil class="mr-1.5 size-3.5" /> Edit
      </Button>
      <Button variant="default" size="sm">
        <ArrowRightCircle class="mr-1.5 size-3.5" /> Convert
      </Button>
    </div>
  {/snippet}
</PageHeader>

<!-- Stage stepper -->
<div class="px-7 pb-3 md:px-8">
  <StageStepper stages={stepperStages} current={normalizedStatus} />
</div>

<!-- Tabs -->
<Tabs.Root bind:value={tab} class="px-7 md:px-8">
  <Tabs.List class="">
    <Tabs.Trigger class="" value="overview">Overview</Tabs.Trigger>
    <Tabs.Trigger class="" value="activity">
      Activity
      <span
        class="ml-1.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[color:var(--bg-elevated)] px-1 text-[10px] tabular-nums text-[color:var(--text-subtle)]"
      >
        {timelineItems.length}
      </span>
    </Tabs.Trigger>
    <Tabs.Trigger class="" value="files">
      Files
      <span
        class="ml-1.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[color:var(--bg-elevated)] px-1 text-[10px] tabular-nums text-[color:var(--text-subtle)]"
      >
        {attachments.length}
      </span>
    </Tabs.Trigger>
  </Tabs.List>

  <Tabs.Content class="" value="overview">
    {#snippet efRow(label, props)}
      <div class="grid grid-cols-[120px_minmax(0,1fr)] items-center gap-3 py-0.5">
        <span class="text-[12px] text-[color:var(--text-subtle)]">{label}</span>
        <EditableField {recordId} api={leadsApi} {...props} />
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
            value={lead?.description}
            {recordId}
            api={leadsApi}
            emptyText="Click to add notes — Markdown supported (# H1, ## H2, **bold**, - lists)."
          />
        </SectionCard>

        <!-- Custom fields -->
        {#if customFieldDefinitions.length > 0}
          <CustomFieldsPanel
            target="Lead"
            definitions={customFieldDefinitions}
            values={customFieldValues}
            title="Custom Fields"
          />
        {/if}

        <!-- Person -->
        <SectionCard title="Person">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Salutation', { type: 'select', field: 'salutation', value: lead?.salutation, options: salutationOptions, placeholder: '—' })}
            {@render efRow('First name', { field: 'first_name', value: lead?.first_name, placeholder: 'Add first name' })}
            {@render efRow('Last name', { field: 'last_name', value: lead?.last_name, placeholder: 'Add last name' })}
            {@render efRow('Job title', { field: 'job_title', value: lead?.job_title, placeholder: 'Add job title' })}
            {@render efRow('Company', { field: 'company_name', value: lead?.company_name, placeholder: 'Add company' })}
          </div>
        </SectionCard>

        <!-- Contact -->
        <SectionCard title="Contact">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Email', { type: 'email', field: 'email', value: lead?.email, placeholder: 'Add email' })}
            {@render efRow('Phone', { type: 'tel', field: 'phone', value: lead?.phone, placeholder: 'Add phone' })}
            {@render efRow('Website', { type: 'url', field: 'website', value: lead?.website, placeholder: 'Add website' })}
            {@render efRow('LinkedIn', { type: 'url', field: 'linkedin_url', value: lead?.linkedin_url, placeholder: 'Add LinkedIn URL' })}
          </div>
        </SectionCard>

        <!-- Deal -->
        <SectionCard title="Deal">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Deal value', { type: 'number', field: 'opportunity_amount', value: lead?.opportunity_amount, placeholder: '0', format: fmtMoney })}
            {@render efRow('Currency', { type: 'select', field: 'currency', value: lead?.currency, options: currencyOptions, placeholder: '—' })}
            {@render efRow('Probability', { type: 'number', field: 'probability', value: lead?.probability, placeholder: '0', format: fmtPct })}
            {@render efRow('Close date', { type: 'date', field: 'close_date', value: lead?.close_date, format: fmtDate })}
            {@render efRow('Status', { type: 'select', field: 'status', value: lead?.status, options: statusOptions, placeholder: '—' })}
            {@render efRow('Rating', { type: 'select', field: 'rating', value: lead?.rating, options: ratingOptions, placeholder: '—' })}
            {@render efRow('Source', { type: 'select', field: 'source', value: lead?.source, options: sourceOptions, placeholder: '—' })}
            {@render efRow('Industry', { type: 'select', field: 'industry', value: lead?.industry, options: industryOptions, placeholder: '—' })}
          </div>
        </SectionCard>

        <!-- Address -->
        <SectionCard title="Address">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Street', { field: 'address_line', value: lead?.address_line, placeholder: 'Add street address' })}
            {@render efRow('City', { field: 'city', value: lead?.city, placeholder: 'Add city' })}
            {@render efRow('State', { field: 'state', value: lead?.state, placeholder: 'Add state' })}
            {@render efRow('Postal code', { field: 'postcode', value: lead?.postcode, placeholder: 'Add postal code' })}
            {@render efRow('Country', { type: 'select', field: 'country', value: lead?.country, options: countryOptions, placeholder: '—' })}
          </div>
        </SectionCard>

        <!-- Dates -->
        <SectionCard title="Dates">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Last contact', { type: 'date', field: 'last_contacted', value: lead?.last_contacted, format: fmtDate })}
            {@render efRow('Next follow-up', { type: 'date', field: 'next_follow_up', value: lead?.next_follow_up, format: fmtDate })}
          </div>
        </SectionCard>
      </div>

      <!-- Right rail -->
      <div class="flex flex-col gap-6">
        <!-- Record meta (read-only) -->
        <SectionCard title="Record">
          <dl class="grid grid-cols-1 gap-y-2.5 text-[12px]">
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Created</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {lead?.created_at || lead?.created_on
                  ? formatDate(lead.created_at || lead.created_on)
                  : '—'}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Updated</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {lead?.updated_at ? formatRelativeDate(lead.updated_at) : '—'}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Created by</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {lead?.created_by?.email || '—'}
              </dd>
            </div>
          </dl>
        </SectionCard>

        <!-- People -->
        <SectionCard title="People">
          <div class="flex flex-col gap-3 text-[12px]">
            <div>
              <div class="mb-1.5 flex items-center gap-1 text-[11px] text-[color:var(--text-subtle)]">
                <UserCheck class="size-3" /> Assigned to
              </div>
              {#if assignedUsers.length === 0}
                <p class="italic text-[color:var(--text-subtle)]">Unassigned</p>
              {:else}
                <ul class="flex flex-col gap-1.5">
                  {#each assignedUsers as user (user.id)}
                    <li class="flex items-center gap-2">
                      <span
                        class="flex size-5 items-center justify-center rounded-full bg-[color:var(--color-primary-light)] text-[9px] font-semibold text-[color:var(--color-primary-default)]"
                      >
                        {getNameInitials(user.email, '')}
                      </span>
                      <span class="truncate text-[color:var(--text-muted)]">{user.email}</span>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
            {#if teams.length > 0}
              <div>
                <div class="mb-1.5 flex items-center gap-1 text-[11px] text-[color:var(--text-subtle)]">
                  <Users class="size-3" /> Teams
                </div>
                <div class="flex flex-wrap gap-1.5">
                  {#each teams as team (team.id)}
                    <Badge
                      variant="secondary"
                      class="bg-[color:var(--bg-elevated)] text-[color:var(--text-muted)]"
                    >
                      {team.name}
                    </Badge>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </SectionCard>

        <!-- Tags -->
        <SectionCard title="Tags">
          {#if tags.length === 0}
            <p class="text-[12px] italic text-[color:var(--text-subtle)]">No tags.</p>
          {:else}
            <div class="flex flex-wrap gap-1.5">
              {#each tags as tag, i (tag.id ?? tag.slug ?? tag.name ?? i)}
                <Badge
                  variant="secondary"
                  class="bg-[color:var(--bg-elevated)] text-[color:var(--text-muted)]"
                >
                  {tag.name}
                </Badge>
              {/each}
            </div>
          {/if}
        </SectionCard>

        <!-- Activity preview -->
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
                  {#snippet text()}Lead created{/snippet}
                </TimelineItem>
              {/if}
            {/each}
          </Timeline>
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
                <TimelineItem
                  variant="violet"
                  time={item.ts ? formatRelativeDate(item.ts) : ''}
                  quote={item.payload.comment || ''}
                >
                  {#snippet icon()}<MessageSquare class="size-3.5" />{/snippet}
                  {#snippet text()}<strong
                      >{item.payload.commented_by_user || 'Someone'}</strong
                    > commented{/snippet}
                </TimelineItem>
              {:else if item.kind === 'attachment'}
                <TimelineItem time={item.ts ? formatRelativeDate(item.ts) : ''}>
                  {#snippet icon()}<Paperclip class="size-3.5" />{/snippet}
                  {#snippet text()}<strong>{item.payload.created_by_user || 'Someone'}</strong>
                    uploaded <strong>{item.payload.file_name || 'a file'}</strong>{/snippet}
                </TimelineItem>
              {:else}
                <TimelineItem variant="success" time={item.ts ? formatRelativeDate(item.ts) : ''}>
                  {#snippet icon()}<Calendar class="size-3.5" />{/snippet}
                  {#snippet text()}Lead created{/snippet}
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
        <AttachmentPanel entity="leads" recordId={lead.id} {attachments} />
      </SectionCard>
    </div>
  </Tabs.Content>
</Tabs.Root>
