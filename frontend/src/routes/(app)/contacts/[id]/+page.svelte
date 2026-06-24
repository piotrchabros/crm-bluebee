<script>
  import { goto } from '$app/navigation';
  import { Mail, Phone, Building2, Pencil, Paperclip, MessageSquare } from '@lucide/svelte';
  import { PageHeader } from '$lib/components/layout';
  import { SectionCard } from '$lib/components/ui/section-card/index.js';
  import * as Tabs from '$lib/components/ui/tabs/index.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import AttachmentPanel from '$lib/components/attachments/AttachmentPanel.svelte';
  import RecordComments from '$lib/components/comments/RecordComments.svelte';
  import { formatRelativeDate, formatDate } from '$lib/utils/formatting.js';
  import { COUNTRIES } from '$lib/constants/lead-choices.js';
  import { contacts as contactsApi } from '$lib/api.js';
  import { EditableField } from '$lib/components/ui/editable-field';
  import { RelationLink } from '$lib/components/ui/relation-link';

  /** @type {{ data: { contact: any, attachments: any[], comments: any[], tasks: any[], commentPermission: boolean } }} */
  let { data } = $props();

  const contact = $derived(data.contact || {});
  const attachments = $derived(data.attachments || []);
  const comments = $derived(data.comments || []);

  const fullName = $derived(
    [contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Contact'
  );

  const assignedUsers = $derived(
    (contact.assigned_to || [])
      .map((/** @type {any} */ p) => p?.user_details?.email || p?.user?.email || p?.email)
      .filter(Boolean)
  );

  // --- Inline-edit support ---
  const recordId = $derived(contact?.id);

  // Country option values are the exact backend ISO choice keys the serializer
  // accepts (see backend/common/utils.py COUNTRIES + contacts/models.py).
  const countryOptions = COUNTRIES.filter((c) => c.value).map((c) => ({
    value: c.value,
    label: c.label
  }));

  // do_not_call is a real boolean on the model; the select draft is a string so
  // transform converts it back to a boolean before PATCH.
  const boolOptions = [
    { value: 'false', label: 'No' },
    { value: 'true', label: 'Yes' }
  ];
  const toBool = (/** @type {any} */ v) => v === true || v === 'true';

  // Account relation: the detail serializer returns `account` as a bare UUID PK
  // (no nested name); link to the account detail page when present.
  const accountId = $derived(contact?.account?.id || contact?.account || '');
  const accountName = $derived(contact?.account?.name || (accountId ? 'View account' : ''));

  let tab = $state('overview');
</script>

<svelte:head>
  <title>{fullName} · BottleCRM</title>
</svelte:head>

<PageHeader
  title={fullName}
  subtitle={contact?.title || ''}
  breadcrumb={[{ label: 'Contacts', href: '/contacts' }, { label: fullName }]}
>
  {#snippet meta()}
    <div
      class="flex flex-wrap items-center gap-3 text-[12px] leading-none text-[color:var(--text-subtle)]"
    >
      {#if contact?.created_at}
        <span>Created {formatRelativeDate(contact.created_at)}</span>
      {/if}
      {#if contact?.organization}
        <span>·</span>
        <span class="flex items-center gap-1"><Building2 class="size-3" />{contact.organization}</span>
      {/if}
    </div>
  {/snippet}

  {#snippet actions()}
    <div class="flex items-center gap-1.5">
      {#if contact?.email}
        <Button variant="ghost" size="icon" aria-label="Email" href="mailto:{contact.email}">
          <Mail class="size-4" />
        </Button>
      {/if}
      {#if contact?.phone}
        <Button variant="ghost" size="icon" aria-label="Call" href="tel:{contact.phone}">
          <Phone class="size-4" />
        </Button>
      {/if}
      <Button
        variant="outline"
        size="sm"
        onclick={() => contact?.id && goto(`/contacts?view=${contact.id}`)}
      >
        <Pencil class="mr-1.5 size-3.5" /> Edit
      </Button>
    </div>
  {/snippet}
</PageHeader>

<Tabs.Root bind:value={tab} class="px-7 md:px-8">
  <Tabs.List class="">
    <Tabs.Trigger class="" value="overview">Overview</Tabs.Trigger>
    <Tabs.Trigger class="" value="activity">
      Activity
      {#if comments.length}<span class="ml-1 text-[color:var(--text-subtle)]">{comments.length}</span>{/if}
    </Tabs.Trigger>
    <Tabs.Trigger class="" value="files">
      Files
      {#if attachments.length}<span class="ml-1 text-[color:var(--text-subtle)]">{attachments.length}</span>{/if}
    </Tabs.Trigger>
  </Tabs.List>

  <Tabs.Content class="" value="overview">
    {#snippet efRow(label, props)}
      <div class="grid grid-cols-[120px_minmax(0,1fr)] items-center gap-3 py-0.5">
        <span class="text-[12px] text-[color:var(--text-subtle)]">{label}</span>
        <EditableField {recordId} api={contactsApi} {...props} />
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
            value={contact?.description}
            {recordId}
            api={contactsApi}
            emptyText="Click to add notes — Markdown supported (# H1, ## H2, **bold**, - lists)."
          />
        </SectionCard>

        <!-- Person -->
        <SectionCard title="Person">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('First name', { field: 'first_name', value: contact?.first_name, placeholder: 'Add first name' })}
            {@render efRow('Last name', { field: 'last_name', value: contact?.last_name, placeholder: 'Add last name' })}
            {@render efRow('Job title', { field: 'title', value: contact?.title, placeholder: 'Add job title' })}
            {@render efRow('Department', { field: 'department', value: contact?.department, placeholder: 'Add department' })}
            {@render efRow('Company', { field: 'organization', value: contact?.organization, placeholder: 'Add company' })}
          </div>
        </SectionCard>

        <!-- Contact -->
        <SectionCard title="Contact">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Email', { type: 'email', field: 'email', value: contact?.email, placeholder: 'Add email' })}
            {@render efRow('Phone', { type: 'tel', field: 'phone', value: contact?.phone, placeholder: 'Add phone' })}
            {@render efRow('LinkedIn', { type: 'url', field: 'linkedin_url', value: contact?.linkedin_url, placeholder: 'Add LinkedIn URL' })}
            {@render efRow('Do not call', { type: 'select', field: 'do_not_call', value: contact?.do_not_call ? 'true' : 'false', options: boolOptions, transform: toBool })}
          </div>
        </SectionCard>

        <!-- Address -->
        <SectionCard title="Address">
          <div class="flex flex-col divide-y divide-[color:var(--border)]/40">
            {@render efRow('Street', { field: 'address_line', value: contact?.address_line, placeholder: 'Add street address' })}
            {@render efRow('City', { field: 'city', value: contact?.city, placeholder: 'Add city' })}
            {@render efRow('State', { field: 'state', value: contact?.state, placeholder: 'Add state' })}
            {@render efRow('Postal code', { field: 'postcode', value: contact?.postcode, placeholder: 'Add postal code' })}
            {@render efRow('Country', { type: 'select', field: 'country', value: contact?.country, options: countryOptions, placeholder: '—' })}
          </div>
        </SectionCard>
        <!-- Comments -->
        <SectionCard title="Comments">
          <RecordComments comments={data.comments || []} canComment={data.commentPermission} />
        </SectionCard>
      </div>

      <!-- Right rail -->
      <div class="flex flex-col gap-6">
        <!-- Relationships -->
        <SectionCard title="Relationships">
          <dl class="grid grid-cols-1 gap-y-2.5 text-[12px]">
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Account</dt>
              <dd class="min-w-0 text-right">
                {#if accountId}
                  <RelationLink
                    value={accountName}
                    href={`/accounts/${accountId}`}
                    label="account"
                  />
                {:else}
                  <span class="text-[color:var(--text-subtle)]">—</span>
                {/if}
              </dd>
            </div>
            {#if assignedUsers.length}
              <div class="flex items-baseline justify-between gap-3">
                <dt class="text-[color:var(--text-subtle)]">Assigned to</dt>
                <dd class="min-w-0 truncate text-right text-[color:var(--text-muted)]">
                  {assignedUsers.join(', ')}
                </dd>
              </div>
            {/if}
          </dl>
        </SectionCard>

        <!-- Record meta (read-only) -->
        <SectionCard title="Record">
          <dl class="grid grid-cols-1 gap-y-2.5 text-[12px]">
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Created</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {contact?.created_at ? formatDate(contact.created_at) : '—'}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-3">
              <dt class="text-[color:var(--text-subtle)]">Created by</dt>
              <dd class="truncate text-right text-[color:var(--text-muted)]">
                {contact?.created_by?.email || '—'}
              </dd>
            </div>
          </dl>
        </SectionCard>
      </div>
    </div>
  </Tabs.Content>

  <Tabs.Content class="" value="activity">
    <div class="pt-4 pb-8">
      <SectionCard title="Comments">
        {#if comments.length === 0}
          <p class="text-[12px] italic text-[color:var(--text-subtle)]">No activity yet.</p>
        {:else}
          <ul class="flex flex-col gap-3">
            {#each comments as c (c.id)}
              <li class="flex gap-2.5 text-[12px]">
                <MessageSquare class="mt-0.5 size-3.5 shrink-0 text-[color:var(--text-subtle)]" />
                <div>
                  <p class="text-[color:var(--text)]">{c.comment}</p>
                  <p class="text-[11px] text-[color:var(--text-subtle)]">
                    {c.commented_by_user || 'Someone'}
                    {c.commented_on ? ` · ${formatRelativeDate(c.commented_on)}` : ''}
                  </p>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      </SectionCard>
    </div>
  </Tabs.Content>

  <Tabs.Content class="" value="files">
    <div class="pt-4 pb-8">
      <SectionCard title="Files">
        <AttachmentPanel entity="contacts" recordId={contact.id} {attachments} />
      </SectionCard>
    </div>
  </Tabs.Content>
</Tabs.Root>
