<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api/client';
  import type { ActivityLog } from '$lib/api/types';

  type MainTab = 'news' | 'agent';
  type EventCategory = 'All' | 'Tasks' | 'Tools' | 'Permissions' | 'Research' | 'Browser' | 'Terminal' | 'Git' | 'Errors' | 'Fallbacks';

  let activeTab: MainTab = 'agent';

  // ─── Real News State ───
  interface NewsItem {
    id: string;
    title: string;
    source: string;
    published_at: string;
    url: string;
    snippet?: string;
  }

  let newsItems: NewsItem[] = [];
  let isNewsLoading = false;
  let newsError = '';

  // ─── Agent Activity State ───
  let activities: ActivityLog[] = [];
  let selectedCategory: EventCategory = 'All';
  let searchQuery = '';
  let selectedEvent: ActivityLog | null = null;
  let isAgentLoading = true;
  let unsubscribeWs: (() => void) | null = null;

  const categories: EventCategory[] = [
    'All', 'Tasks', 'Tools', 'Permissions', 'Research', 'Browser', 'Terminal', 'Git', 'Errors', 'Fallbacks'
  ];

  onMount(async () => {
    await Promise.all([
      loadAuditLogs(),
      loadRealNews()
    ]);
    unsubscribeWs = api.connectWebSocket((evt: any) => {
      handleIncomingWsEvent(evt);
    });
  });

  onDestroy(() => {
    if (unsubscribeWs) unsubscribeWs();
  });

  // ─── Real News Loader ───
  async function loadRealNews() {
    isNewsLoading = true;
    newsError = '';
    try {
      // Primary real news source: BBC News RSS Feed via rss2json
      const res = await fetch('https://api.rss2json.com/v1/api.json?rss_url=https://feeds.bbci.co.uk/news/rss.xml');
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok' && Array.isArray(data.items) && data.items.length > 0) {
          newsItems = data.items.map((item: any, idx: number) => ({
            id: `news_${idx}_${Date.now()}`,
            title: item.title,
            source: data.feed?.title || 'BBC World News',
            published_at: item.pubDate,
            url: item.link,
            snippet: item.description ? item.description.replace(/<[^>]*>?/gm, '').trim() : '',
          }));
          return;
        }
      }

      // Fallback real news source: Hacker News Top Stories API
      const hnRes = await fetch('https://hacker-news.firebaseio.com/v0/topstories.json');
      if (hnRes.ok) {
        const storyIds: number[] = await hnRes.json();
        const topIds = storyIds.slice(0, 15);
        const stories = await Promise.all(
          topIds.map((id) =>
            fetch(`https://hacker-news.firebaseio.com/v0/item/${id}.json`)
              .then((r) => r.json())
              .catch(() => null)
          )
        );

        newsItems = stories
          .filter((s) => s && s.title && (s.url || s.id))
          .map((s) => ({
            id: `hn_${s.id}`,
            title: s.title,
            source: s.by ? `Hacker News (${s.by})` : 'Hacker News',
            published_at: new Date(s.time * 1000).toISOString(),
            url: s.url || `https://news.ycombinator.com/item?id=${s.id}`,
            snippet: s.text ? s.text.replace(/<[^>]*>?/gm, '').trim() : `Score: ${s.score || 0} | Comments: ${s.descendants || 0}`
          }));
        return;
      }

      throw new Error('Unable to connect to live news sources.');
    } catch (err: any) {
      newsError = err.message || 'Failed to fetch current world news.';
    } finally {
      isNewsLoading = false;
    }
  }

  // ─── Agent Activity Loader & Filtering ───
  function isHeartbeatEvent(evt: any): boolean {
    const type = String(evt.event_type || evt.event || evt.type || '').toUpperCase();
    const msg = String(evt.message || evt.operation || '').toUpperCase();
    return type === 'PULSE' || type === 'HEARTBEAT' || msg === 'PULSE' || msg === 'HEARTBEAT';
  }

  async function loadAuditLogs() {
    isAgentLoading = true;
    try {
      const logs = await api.getAuditLogs(100).catch(() => []);
      // Filter internal heartbeat / PULSE events from the user-facing feed
      activities = logs.filter((log) => !isHeartbeatEvent(log));
    } catch {
      // Graceful fallback
    } finally {
      isAgentLoading = false;
    }
  }

  function handleIncomingWsEvent(evt: any) {
    if (!evt || isHeartbeatEvent(evt)) return;

    const newLog: ActivityLog = {
      id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      task_id: evt.task_id || evt.details?.task_id || undefined,
      event_type: evt.event || evt.type || 'agent_event',
      message: evt.message || evt.operation || JSON.stringify(evt),
      status: evt.status || 'done',
      details: evt.details || evt,
      timestamp: new Date().toISOString(),
    };

    activities = [newLog, ...activities];
  }

  function matchesCategory(act: ActivityLog, cat: EventCategory): boolean {
    if (cat === 'All') return true;
    const msg = (act.message || '').toLowerCase();
    const evt = (act.event_type || '').toLowerCase();
    const tool = (act.details?.tool_name || act.details?.tool || '').toLowerCase();

    switch (cat) {
      case 'Tasks':
        return evt.includes('task') || evt.includes('plan') || evt.includes('step');
      case 'Tools':
        return evt.includes('tool') || Boolean(tool);
      case 'Permissions':
        return evt.includes('permission') || evt.includes('allow') || evt.includes('deny');
      case 'Research':
        return evt.includes('research') || msg.includes('tavily') || msg.includes('brave');
      case 'Browser':
        return evt.includes('browser') || tool.includes('browser') || msg.includes('playwright');
      case 'Terminal':
        return evt.includes('terminal') || tool.includes('terminal') || tool.includes('command');
      case 'Git':
        return evt.includes('git') || tool.includes('git');
      case 'Errors':
        return evt.includes('error') || evt.includes('fail') || act.status === 'failed' || act.status === 'error';
      case 'Fallbacks':
        return evt.includes('fallback') || msg.includes('fallback');
      default:
        return true;
    }
  }

  $: filteredActivities = activities.filter((act) => {
    const matchCat = matchesCategory(act, selectedCategory);
    if (!searchQuery.trim()) return matchCat;
    const q = searchQuery.toLowerCase();
    const matchSearch = (act.message || '').toLowerCase().includes(q) ||
                        (act.event_type || '').toLowerCase().includes(q) ||
                        (act.task_id || '').toLowerCase().includes(q);
    return matchCat && matchSearch;
  });

  function getBadgeClass(act: ActivityLog) {
    const status = (act.status || act.event_type || '').toLowerCase();
    if (status.includes('fail') || status.includes('error') || status.includes('deny')) {
      return 'bg-[#5c1d24] text-[#f8d7da] border border-[#842029] font-semibold';
    }
    if (status.includes('permission') || status.includes('wait')) {
      return 'bg-[#533f03] text-[#fff3cd] border border-[#997404] font-semibold';
    }
    if (status.includes('complete') || status.includes('success') || status.includes('done')) {
      return 'bg-[#1b4332] text-[#d8f3dc] border border-[#2d6a4f] font-semibold';
    }
    return 'bg-[#352928] text-[#f3dedc] border border-[#514442] font-semibold';
  }

  function formatTime(isoString: string): string {
    try {
      const d = new Date(isoString);
      return isNaN(d.getTime()) ? isoString : d.toLocaleString();
    } catch {
      return isoString;
    }
  }
</script>

<main class="ml-56 pt-12 min-h-[calc(100vh-48px)] w-[calc(100vw-14rem)] bg-background flex flex-col select-none overflow-y-auto px-6 py-8 animate-page-enter">
  <div class="w-full max-w-[1000px] mx-auto space-y-6">
    
    <!-- Title & Parent Sub-Tabs -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant/40 pb-4">
      <div>
        <h1 class="font-headline-md text-[22px] text-primary font-semibold tracking-tight">Activity</h1>
        <p class="font-ui-main text-[13px] text-on-surface-variant/70 mt-1">
          {activeTab === 'news' ? 'Live current-world news stream.' : 'Real-time Cocoa agent events and execution logs.'}
        </p>
      </div>

      <!-- Parent Sub-Tabs Toggle -->
      <div class="inline-flex p-1 bg-[#e8d2cc] border border-[#d6b2aa] rounded-lg gap-1">
        <button
          type="button"
          onclick={() => activeTab = 'news'}
          class="{activeTab === 'news' ? 'btn-primary btn-sm' : 'btn-ghost btn-sm text-[#1f1514]'}"
        >
          <span class="material-symbols-outlined text-[16px] {activeTab === 'news' ? 'text-white' : 'text-[#1f1514]'}">newspaper</span>
          Real News
        </button>
        <button
          type="button"
          onclick={() => activeTab = 'agent'}
          class="{activeTab === 'agent' ? 'btn-primary btn-sm' : 'btn-ghost btn-sm text-[#1f1514]'}"
        >
          <span class="material-symbols-outlined text-[16px] {activeTab === 'agent' ? 'text-white' : 'text-[#1f1514]'}">smart_toy</span>
          Agent Activity
        </button>
      </div>
    </div>

    <!-- ───────────────────────────────────────────────────────────── -->
    <!-- SUB-TAB 1: REAL NEWS                                           -->
    <!-- ───────────────────────────────────────────────────────────── -->
    {#if activeTab === 'news'}
      <div class="space-y-4">
        {#if isNewsLoading}
          <div class="space-y-3">
            {#each Array(4) as _}
              <div class="bg-surface border border-outline-variant/60 rounded-lg p-4 animate-skeleton">
                <div class="h-4 bg-surface-container-high rounded w-3/4 mb-2"></div>
                <div class="h-3 bg-surface-container-high rounded w-1/4"></div>
              </div>
            {/each}
          </div>
        {:else if newsError}
          <div class="bg-surface border border-outline-variant/60 rounded-lg p-8 text-center space-y-3">
            <span class="material-symbols-outlined text-[32px] text-error">cloud_off</span>
            <p class="font-ui-medium text-[13px] text-primary">{newsError}</p>
            <button
              type="button"
              onclick={loadRealNews}
              class="px-4 py-1.5 bg-secondary text-on-secondary font-ui-medium text-[12px] rounded-md hover:bg-secondary-container transition-colors"
            >
              Retry Connection
            </button>
          </div>
        {:else if newsItems.length === 0}
          <div class="bg-surface border border-outline-variant/60 rounded-lg p-8 text-center text-on-surface-variant/60 font-ui-main text-[13px]">
            No live news items currently available.
          </div>
        {:else}
          <div class="bg-surface border border-outline-variant/60 rounded-lg divide-y divide-outline-variant/40 overflow-hidden shadow-2xs">
            {#each newsItems as item}
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                class="px-5 py-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-surface-container-lowest transition-colors group block"
              >
                <div class="space-y-1.5 max-w-3xl">
                  <h2 class="font-ui-medium text-[14px] text-primary group-hover:text-secondary transition-colors leading-snug">
                    {item.title}
                  </h2>
                  {#if item.snippet}
                    <p class="font-ui-main text-[12px] text-on-surface-variant/80 line-clamp-2 leading-relaxed">
                      {item.snippet}
                    </p>
                  {/if}
                  <div class="flex items-center gap-3 pt-1">
                    <span class="font-label-caps text-[10px] text-secondary font-semibold uppercase tracking-wider bg-surface-container-high px-2 py-0.5 rounded">
                      {item.source}
                    </span>
                    <span class="font-status-log text-[11px] text-on-surface-variant/50">
                      {formatTime(item.published_at)}
                    </span>
                  </div>
                </div>

                <div class="flex items-center gap-1 text-secondary font-ui-medium text-[12px] shrink-0 opacity-80 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all">
                  <span>Read Article</span>
                  <span class="material-symbols-outlined text-[16px]">open_in_new</span>
                </div>
              </a>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- ───────────────────────────────────────────────────────────── -->
    <!-- SUB-TAB 2: AGENT ACTIVITY                                      -->
    <!-- ───────────────────────────────────────────────────────────── -->
    {#if activeTab === 'agent'}
      <div class="space-y-4">
        
        <!-- Category Filters & Search -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-1.5">
            {#each categories as cat}
              <button
                type="button"
                onclick={() => selectedCategory = cat}
                class="{selectedCategory === cat ? 'btn-primary btn-pill btn-sm' : 'btn-secondary btn-pill btn-sm'}"
              >
                {cat}
              </button>
            {/each}
          </div>

          <div class="relative min-w-[220px]">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[16px] text-on-surface-variant/60">search</span>
            <input
              type="text"
              bind:value={searchQuery}
              placeholder="Filter events..."
              class="w-full bg-surface border border-outline-variant/60 rounded-md pl-9 pr-3 py-1.5 text-[12px] font-ui-main text-primary placeholder:text-on-surface-variant/50 focus:outline-none focus:border-secondary"
            />
          </div>
        </div>

        <!-- Event List -->
        <div class="bg-surface border border-outline-variant/60 rounded-lg divide-y divide-outline-variant/40 overflow-hidden shadow-2xs">
          {#if filteredActivities.length > 0}
            {#each filteredActivities as act}
              <div
                onclick={() => selectedEvent = act}
                onkeydown={(e) => e.key === 'Enter' && (selectedEvent = act)}
                role="button"
                tabindex={0}
                class="px-4 py-3 flex items-center justify-between hover:bg-surface-container-lowest transition-colors cursor-pointer group"
              >
                <div class="flex items-center gap-3 min-w-0 pr-4">
                  <span class="material-symbols-outlined text-[18px] text-secondary shrink-0">smart_toy</span>
                  <div class="min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-ui-medium text-[13px] text-primary truncate">{act.message}</span>
                      {#if act.task_id}
                        <span class="font-status-log text-[10px] text-on-surface-variant/60 bg-surface-container-high px-1.5 py-0.5 rounded shrink-0">
                          Task: {act.task_id.substring(0, 8)}
                        </span>
                      {/if}
                    </div>
                    <span class="font-status-log text-[10px] text-on-surface-variant/50 block mt-0.5">
                      {formatTime(act.timestamp)}
                    </span>
                  </div>
                </div>

                <div class="flex items-center gap-3 shrink-0">
                  <span class="px-2 py-0.5 rounded text-[10px] font-label-caps uppercase tracking-wider border {getBadgeClass(act)}">
                    {act.event_type || act.status || 'EVENT'}
                  </span>
                  <span class="material-symbols-outlined text-[16px] text-on-surface-variant/50 group-hover:translate-x-0.5 transition-transform">chevron_right</span>
                </div>
              </div>
            {/each}
          {:else if isAgentLoading}
            <div class="p-8 text-center text-on-surface-variant/60 font-ui-main text-[13px]">
              Loading agent activity event stream...
            </div>
          {:else}
            <div class="p-8 text-center text-on-surface-variant/60 font-ui-main text-[13px]">
              No agent activity events match the selected filter query.
            </div>
          {/if}
        </div>

      </div>
    {/if}

  </div>

  <!-- Event Details Modal / Drawer -->
  {#if selectedEvent}
    <div class="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div class="bg-surface border border-outline-variant/80 rounded-xl p-6 w-full max-w-[600px] space-y-4 shadow-xl animate-scale-in">
        <div class="flex items-center justify-between border-b border-outline-variant/40 pb-3">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[20px] text-secondary">info</span>
            <h2 class="font-headline-md text-[16px] text-primary font-semibold">Event Telemetry Details</h2>
          </div>
          <button type="button" onclick={() => selectedEvent = null} class="text-on-surface-variant hover:text-primary">
            <span class="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        <div class="space-y-3 font-ui-main text-[12px]">
          <div class="flex justify-between border-b border-outline-variant/30 py-1">
            <span class="text-on-surface-variant font-medium">Timestamp</span>
            <span class="font-mono text-primary">{formatTime(selectedEvent.timestamp)}</span>
          </div>

          <div class="flex justify-between border-b border-outline-variant/30 py-1">
            <span class="text-on-surface-variant font-medium">Event Type</span>
            <span class="font-mono text-primary">{selectedEvent.event_type || 'N/A'}</span>
          </div>

          {#if selectedEvent.task_id}
            <div class="flex justify-between border-b border-outline-variant/30 py-1">
              <span class="text-on-surface-variant font-medium">Task ID</span>
              <span class="font-mono text-secondary">{selectedEvent.task_id}</span>
            </div>
          {/if}

          <div class="flex justify-between border-b border-outline-variant/30 py-1">
            <span class="text-on-surface-variant font-medium">Status</span>
            <span class="font-mono text-primary">{selectedEvent.status || 'done'}</span>
          </div>

          <div class="space-y-1 pt-1">
            <span class="text-on-surface-variant font-medium block">Message</span>
            <div class="bg-surface-container-high border border-outline-variant/50 rounded p-2.5 font-mono text-[11px] text-primary leading-relaxed break-words">
              {selectedEvent.message}
            </div>
          </div>

          {#if selectedEvent.details}
            <div class="space-y-1 pt-1">
              <span class="text-on-surface-variant font-medium block font-medium">Safe Event Metadata</span>
              <pre class="bg-surface-container-high border border-outline-variant/50 rounded p-2.5 font-mono text-[10px] text-primary overflow-x-auto max-h-48">
                {JSON.stringify(selectedEvent.details, null, 2)}
              </pre>
            </div>
          {/if}
        </div>

        <div class="flex justify-end pt-2">
          <button type="button" onclick={() => selectedEvent = null} class="btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  {/if}
</main>
