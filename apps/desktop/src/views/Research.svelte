<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api/client';
  import type { ResearchSession, ResearchSource, ResearchFinding } from '$lib/api/types';

  let sessions: ResearchSession[] = [];
  let currentSession: ResearchSession | null = null;
  let isLoading = true;
  let isSubmitting = false;
  let errorMsg = '';
  let newResearchQuery = '';
  let searchQuery = '';
  let unsubscribeWs: (() => void) | null = null;

  async function loadSessions() {
    try {
      sessions = await api.getResearchSessions();
      if (sessions.length > 0) {
        if (!currentSession) {
          currentSession = sessions[0];
        } else {
          const updated = sessions.find((s) => s.id === currentSession?.id);
          if (updated) currentSession = updated;
        }
      }
    } catch (err: any) {
      errorMsg = err.message || 'Failed to load research sessions';
    } finally {
      isLoading = false;
    }
  }

  async function handleStartResearch(e?: Event) {
    if (e) e.preventDefault();
    if (!newResearchQuery.trim() || isSubmitting) return;
    isSubmitting = true;
    errorMsg = '';
    try {
      const session = await api.runResearch(newResearchQuery.trim());
      newResearchQuery = '';
      currentSession = session;
      await loadSessions();
    } catch (err: any) {
      errorMsg = err.message || 'Failed to start research session';
    } finally {
      isSubmitting = false;
    }
  }

  async function handleCancelSession(id: string) {
    try {
      const updated = await api.cancelResearch(id);
      currentSession = updated;
      await loadSessions();
    } catch (err: any) {
      console.error('Failed to cancel session:', err);
    }
  }

  function handleWsEvent(msg: any) {
    if (!msg || !msg.event || !msg.event.startsWith('research.')) return;
    
    loadSessions();

    if (currentSession && msg.data?.session_id === currentSession.id) {
      api.getResearchSession(currentSession.id).then((refreshed) => {
        currentSession = refreshed;
      }).catch(console.error);
    }
  }

  $: filteredSessions = sessions.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.query.toLowerCase().includes(searchQuery.toLowerCase())
  );

  onMount(() => {
    loadSessions();
    unsubscribeWs = api.connectWebSocket(handleWsEvent);
  });

  onDestroy(() => {
    if (unsubscribeWs) unsubscribeWs();
  });
</script>

<div class="ml-56 flex flex-col h-screen overflow-hidden bg-background">
  <!-- TopBar Header -->
  <header class="bg-background flex justify-between items-center h-12 px-4 w-full z-10 sticky top-0 border-b border-outline-variant/40 select-none">
    <div class="flex items-center gap-3">
      <h2 class="font-headline-md text-[16px] text-primary font-semibold tracking-tight">Research Workspace</h2>
      <span class="font-status-log text-[10px] bg-surface-container-high text-on-surface-variant px-1.5 py-0.5 rounded border border-outline-variant/40">
        Multi-Provider Engine
      </span>
    </div>
    <div class="flex items-center gap-2">
      <div class="relative">
        <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-outline text-[16px]">search</span>
        <input
          bind:value={searchQuery}
          class="pl-8 pr-3 py-1 bg-surface-container-low border border-outline-variant/50 rounded-md focus:border-secondary focus:outline-none font-ui-main text-[12px] text-on-background placeholder:text-outline w-56 transition-colors h-7"
          placeholder="Filter research sessions..."
          type="text"
        />
      </div>
    </div>
  </header>

  <!-- Main Area -->
  <main class="flex-1 overflow-hidden flex flex-col p-4 pt-3 gap-3">
    <!-- Compact Quick Launcher Bar -->
    <section class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-2 shadow-sm shrink-0">
      <form onsubmit={handleStartResearch} class="flex items-center gap-2">
        <div class="relative flex-1">
          <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-secondary text-[18px]">auto_awesome</span>
          <input
            bind:value={newResearchQuery}
            disabled={isSubmitting}
            class="w-full pl-9 pr-3 py-1.5 bg-surface/50 border border-outline-variant/50 rounded-md font-ui-main text-[13px] text-on-background placeholder:text-outline focus:outline-none focus:border-secondary transition-all h-8"
            placeholder="Enter research topic, technology comparison, or claim to verify..."
            type="text"
          />
        </div>
        <button
          type="submit"
          disabled={isSubmitting || !newResearchQuery.trim()}
          class="bg-primary hover:bg-primary-container disabled:opacity-50 text-on-primary font-ui-medium text-[12px] px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors shrink-0 h-8"
        >
          {#if isSubmitting}
            <span class="material-symbols-outlined animate-spin text-[16px]">sync</span>
            Starting...
          {:else}
            <span class="material-symbols-outlined text-[16px]">travel_explore</span>
            Run Engine
          {/if}
        </button>
      </form>
    </section>

    {#if isLoading}
      <div class="flex-1 flex items-center justify-center font-ui-main text-[13px] text-on-surface-variant animate-pulse">
        Connecting to Cocoa Research Engine...
      </div>
    {:else if errorMsg}
      <div class="flex-1 flex items-center justify-center">
        <div class="bg-error/10 border border-error/20 text-error rounded-md p-4 text-center max-w-md">
          <span class="material-symbols-outlined text-3xl mb-1">error_outline</span>
          <p class="font-ui-medium text-[13px]">{errorMsg}</p>
        </div>
      </div>
    {:else if !currentSession}
      <div class="flex-1 flex flex-col items-center justify-center text-center border border-dashed border-outline-variant/60 rounded-md p-8">
        <span class="material-symbols-outlined text-4xl text-outline-variant mb-2">find_in_page</span>
        <h3 class="font-headline-md text-[18px] text-primary mb-1">No Research Sessions</h3>
        <p class="font-ui-main text-[13px] text-on-surface-variant max-w-md">
          Run an autonomous web research session using the bar above to plan, gather evidence from web providers, verify claims, and generate synthesis reports.
        </p>
      </div>
    {:else}
      <!-- Compact Active Research Brief -->
      <section class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3 flex justify-between items-center shrink-0 shadow-sm">
        <div class="max-w-3xl">
          <div class="flex items-center gap-2 mb-1 flex-wrap">
            <span class="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-label-caps text-[10px] flex items-center gap-1">
              <span class="material-symbols-outlined text-[12px]">
                {currentSession.status === 'completed' ? 'check_circle' : currentSession.status === 'failed' ? 'error' : 'psychology'}
              </span>
              Status: {currentSession.status.toUpperCase()}
            </span>
            <span class="font-status-log text-[11px] text-on-surface-variant">Session: {currentSession.session_code || currentSession.id.slice(0, 8)}</span>
            {#if currentSession.confidence}
              <span class="bg-surface-container-high text-on-surface-variant px-1.5 py-0.5 rounded font-status-log text-[10px] border border-outline-variant/40">
                Confidence: {currentSession.confidence}%
              </span>
            {/if}
          </div>
          <h2 class="font-headline-md text-[16px] text-primary font-semibold">{currentSession.title}</h2>
          <p class="font-ui-main text-[12px] text-on-surface-variant/80 truncate max-w-xl">Query: {currentSession.query || currentSession.brief}</p>
        </div>

        {#if currentSession && ['planning', 'researching', 'verifying', 'synthesizing'].includes(currentSession.status)}
          <button
            onclick={() => currentSession && handleCancelSession(currentSession.id)}
            class="border border-error/30 text-error hover:bg-error/10 font-ui-medium text-[12px] px-2.5 py-1 rounded-md flex items-center gap-1 transition-colors shrink-0 h-7"
          >
            <span class="material-symbols-outlined text-[16px]">cancel</span>
            Cancel Session
          </button>
        {/if}
      </section>

      <!-- 2-Panel Layout: Insights & Findings | Verified Sources -->
      <div class="flex-1 flex gap-3 overflow-hidden min-h-0">
        <!-- Live Insights & Findings Panel -->
        <section class="flex-1 bg-surface-container-lowest border border-outline-variant/60 rounded-md shadow-sm flex flex-col overflow-hidden">
          <div class="py-2 px-3 border-b border-outline-variant/50 bg-surface/50 sticky top-0 z-10 flex justify-between items-center">
            <h3 class="font-label-caps text-[11px] text-on-surface-variant/90 font-semibold tracking-wide">INSIGHTS & VERIFIED FINDINGS</h3>
            {#if currentSession.status === 'researching' || currentSession.status === 'verifying' || currentSession.status === 'synthesizing'}
              <span class="flex items-center gap-1 text-secondary font-ui-medium text-[11px] animate-pulse">
                <span class="material-symbols-outlined text-[14px]">sync</span>
                Engine Executing...
              </span>
            {/if}
          </div>

          <div class="p-3.5 overflow-y-auto flex-1 font-ui-main text-[13px] text-on-background space-y-3">
            {#if currentSession.synthesis_markdown}
              <div class="prose max-w-none space-y-2 whitespace-pre-wrap text-[13px] leading-[20px]">
                {currentSession.synthesis_markdown}
              </div>
            {:else}
              <div class="text-center text-on-surface-variant/60 py-8 font-ui-main text-[13px]">
                <span class="material-symbols-outlined text-3xl mb-1 block opacity-50">donut_large</span>
                Synthesis report will stream here as research & verification steps complete.
              </div>
            {/if}

            {#if currentSession.findings && currentSession.findings.length > 0}
              <div class="mt-4 pt-3 border-t border-outline-variant/40">
                <h4 class="font-label-caps text-[11px] text-on-surface-variant/80 mb-2 tracking-wider">VERIFIED CLAIMS</h4>
                <div class="space-y-1.5">
                  {#each currentSession.findings as finding}
                    <div class="p-2 rounded-md border border-outline-variant/50 bg-surface/40 flex items-start gap-2">
                      <span class="material-symbols-outlined text-[16px] text-secondary shrink-0 mt-0.5">
                        {finding.is_verified ? 'verified' : 'help_outline'}
                      </span>
                      <div>
                        <p class="font-ui-main text-[12px] text-on-background">{finding.finding_text}</p>
                        <span class="font-status-log text-[10px] text-on-surface-variant/70">
                          Verified ({finding.verification_confidence}) • {finding.supporting_sources ? finding.supporting_sources.length : 0} Sources
                        </span>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </section>

        <!-- Compact Sources Side Panel -->
        <aside class="w-72 flex flex-col gap-2.5 shrink-0 overflow-hidden bg-surface rounded-md border border-outline-variant/60 p-3">
          <div class="flex justify-between items-center pb-2 border-b border-outline-variant/40">
            <h3 class="font-label-caps text-[11px] text-on-surface-variant/90 font-semibold tracking-wide">VERIFIED SOURCES</h3>
            <span class="font-status-log text-[10px] text-on-surface-variant bg-surface-container-high px-1.5 py-0.5 rounded border border-outline-variant/40">
              {currentSession.sources ? currentSession.sources.length : 0}
            </span>
          </div>

          <!-- Sessions Selector Dropdown -->
          {#if filteredSessions.length > 1}
            <div class="pb-1 border-b border-outline-variant/40">
              <label for="switch-session-select" class="font-label-caps text-[10px] text-on-surface-variant/70 block mb-1">Switch Session</label>
              <select
                id="switch-session-select"
                class="w-full bg-surface-container-lowest border border-outline-variant/50 rounded-md p-1 font-ui-main text-[11px] text-on-background focus:outline-none"
                onchange={(e) => {
                  const sel = filteredSessions.find(s => s.id === (e.currentTarget as HTMLSelectElement).value);
                  if (sel) currentSession = sel;
                }}
                value={currentSession.id}
              >
                {#each filteredSessions as s}
                  <option value={s.id}>{s.title} ({s.status})</option>
                {/each}
              </select>
            </div>
          {/if}

          <div class="overflow-y-auto flex-1 flex flex-col gap-2">
            {#if !currentSession.sources || currentSession.sources.length === 0}
              <div class="text-center font-ui-main text-[12px] text-on-surface-variant/60 py-6">
                No sources collected yet.
              </div>
            {:else}
              {#each currentSession.sources as source}
                <div class="p-2 rounded-md border border-outline-variant/50 hover:bg-surface-container-low transition-colors bg-surface-container-lowest">
                  <div class="flex justify-between items-start mb-0.5">
                    <h4 class="font-ui-medium text-[12px] text-primary font-medium line-clamp-2">{source.title}</h4>
                  </div>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="font-ui-main text-[11px] text-secondary hover:underline truncate block mb-1"
                  >
                    {source.domain || source.url}
                  </a>
                  <div class="flex justify-between items-center text-[10px] text-on-surface-variant/70">
                    <span class="bg-surface-container-high px-1 py-0.5 rounded uppercase font-status-log border border-outline-variant/30">
                      {source.provider || 'tavily'}
                    </span>
                    {#if source.relevance}
                      <span>Rel: {Math.round(source.relevance * 100)}%</span>
                    {/if}
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        </aside>
      </div>
    {/if}
  </main>
</div>
