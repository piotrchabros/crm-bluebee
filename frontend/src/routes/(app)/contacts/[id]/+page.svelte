<script>
  import { goto } from '$app/navigation';
  import {
    Mail,
    Phone,
    Building2,
    Briefcase,
    MapPin,
    Pencil,
    Paperclip,
    MessageSquare,
    ExternalLink
  } from '@lucide/svelte';
  import { LinkedinIcon as Linkedin } from '$lib/components/icons';
  import { PageHeader } from '$lib/components/layout';
  import { SectionCard } from '$lib/components/ui/section-card/index.js';
  import * as Tabs from '$lib/components/ui/tabs/index.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import AttachmentPanel from '$lib/components/attachments/AttachmentPanel.svelte';
  import { formatRelativeDate } from '$lib/utils/formatting.js';

  /** @type {{ data: { contact: any, attachments: any[], comments: any[], tasks: any[] } }} */
  let { data } = $props();

  const contact = $derived(data.contact || {});
  const attachments = $derived(data.attachments || []);
  const comments = $derived(data.comments || []);

  const fullName = $derived(
    [contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Contact'
  );
  const address = $derived(
    [contact.address_line, contact.city, contact.state, contact.postcode, contact.country]
      .filter(Boolean)
      .join(', ')
  );
  const assignedUsers = $derived(
    (contact.assigned_to || []).map((/** @type {any} */ p) => p?.user_details?.email || p?.email).filter(Boolean)
  );

  let tab = $state('overview');
</script>

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
    <div class="grid gap-4 pt-4 pb-8 md:grid-cols-2">
      <SectionCard title="Details">
        <dl class="flex flex-col gap-2.5 text-[12px]">
          {#if contact.email}
            <div class="flex items-center gap-2">
              <Mail class="size-3.5 text-[color:var(--text-subtle)]" />
              <a class="hover:underline" href="mailto:{contact.email}">{contact.email}</a>
            </div>
          {/if}
          {#if contact.phone}
            <div class="flex items-center gap-2">
              <Phone class="size-3.5 text-[color:var(--text-subtle)]" />
              <a class="hover:underline" href="tel:{contact.phone}">{contact.phone}</a>
            </div>
          {/if}
          {#if contact.title}
            <div class="flex items-center gap-2">
              <Briefcase class="size-3.5 text-[color:var(--text-subtle)]" />
              <span>{contact.title}{contact.department ? ` · ${contact.department}` : ''}</span>
            </div>
          {/if}
          {#if contact.organization}
            <div class="flex items-center gap-2">
              <Building2 class="size-3.5 text-[color:var(--text-subtle)]" />
              <span>{contact.organization}</span>
            </div>
          {/if}
          {#if contact.linkedin_url}
            <div class="flex items-center gap-2">
              <Linkedin class="size-3.5 text-[color:var(--text-subtle)]" />
              <a class="hover:underline" href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">
                LinkedIn <ExternalLink class="inline size-3" />
              </a>
            </div>
          {/if}
          {#if address}
            <div class="flex items-center gap-2">
              <MapPin class="size-3.5 text-[color:var(--text-subtle)]" />
              <span>{address}</span>
            </div>
          {/if}
          {#if contact.do_not_call}
            <div><Badge variant="outline">Do not call</Badge></div>
          {/if}
        </dl>
      </SectionCard>

      <SectionCard title="Relationships">
        <dl class="flex flex-col gap-2.5 text-[12px]">
          {#if contact.account}
            <div class="flex items-center justify-between">
              <span class="text-[color:var(--text-subtle)]">Account</span>
              <a class="hover:underline" href="/accounts/{contact.account?.id || contact.account}">
                {contact.account?.name || 'View account'}
              </a>
            </div>
          {/if}
          {#if assignedUsers.length}
            <div class="flex items-start justify-between gap-3">
              <span class="text-[color:var(--text-subtle)]">Assigned to</span>
              <span class="text-right">{assignedUsers.join(', ')}</span>
            </div>
          {/if}
          {#if (contact.tags || []).length}
            <div class="flex flex-wrap gap-1.5">
              {#each contact.tags as tag, i (tag.id ?? tag.slug ?? tag.name ?? i)}
                <Badge variant="outline">{tag.name || tag}</Badge>
              {/each}
            </div>
          {/if}
          {#if contact.description}
            <div class="pt-1">
              <span class="text-[color:var(--text-subtle)]">Notes</span>
              <p class="mt-1 whitespace-pre-wrap text-[color:var(--text)]">{contact.description}</p>
            </div>
          {/if}
        </dl>
      </SectionCard>
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
