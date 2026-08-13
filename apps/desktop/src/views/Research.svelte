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
          // preserve selection or update
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

  async function handleStartResearch() {
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
    
    // Refresh sessions when events arrive for active session or new session
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

<div class="ml-64 flex flex-col h-screen overflow-hidden bg-background">
  <!-- TopBar -->
  <header class="bg-background flex justify-between items-center h-16 px-margin-desktop w-full z-10 sticky top-0 border-b border-outline-variant/30">
    <div class="flex items-center gap-md">
      <h2 class="font-headline-md text-headline-md text-primary">Research Workspace</h2>
      <span class="font-status-log text-status-log bg-surface-container-high text-on-surface-variant px-2 py-0.5 rounded">
        Multi-Provider Engine
      </span>
    </div>
    <div class="flex items-center gap-md">
      <div class="relative">
        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">search</span>
        <input
          bind:value={searchQuery}
          class="pl-10 pr-4 py-1.5 bg-transparent border-b-2 border-outline-variant focus:border-secondary focus:outline-none font-ui-main text-ui-main text-on-background placeholder:text-outline w-64 transition-colors"
          placeholder="Filter research sessions..."
          type="text"
        />
      </div>
    </div>
  </header>

  <!-- Main Area -->
  <main class="flex-1 overflow-hidden flex flex-col p-margin-desktop pt-md gap-md">
    <!-- Quick Launcher Bar -->
    <section class="bg-surface-container-lowest border border-outline-variant rounded-xl p-md shadow-[0_4px_24px_rgba(106,91,90,0.04)] shrink-0">
      <form on:submit|preventDefault={handleStartResearch} class="flex items-center gap-md">
        <div class="relative flex-1">
          <span class="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary text-[22px]">auto_awesome</span>
          <input
            bind:value={newResearchQuery}
            disabled={isSubmitting}
            class="w-full pl-11 pr-4 py-2.5 bg-surface/50 border border-outline-variant rounded-lg font-body-reading text-body-reading text-on-background placeholder:text-outline focus:outline-none focus:border-secondary transition-all"
            placeholder="Enter research topic, technology comparison, or claim to verify..."
            type="text"
          />
        </div>
        <button
          type="submit"
          disabled={isSubmitting || !newResearchQuery.trim()}
          class="bg-primary hover:bg-primary/90 disabled:opacity-50 text-on-primary font-ui-medium text-ui-medium px-xl py-2.5 rounded-lg flex items-center gap-xs transition-colors shrink-0"
        >
          {#if isSubmitting}
            <span class="material-symbols-outlined animate-spin text-[18px]">sync</span>
            Starting...
          {:else}
            <span class="material-symbols-outlined text-[18px]">travel_explore</span>
            Run Research Engine
          {/if}
        </button>
      </form>
    </section>

    {#if isLoading}
      <div class="flex-1 flex items-center justify-center font-ui-main text-on-surface-variant animate-pulse">
        Connecting to Cocoa Research Engine...
      </div>
    {:else if errorMsg}
      <div class="flex-1 flex items-center justify-center">
        <div class="bg-error/10 border border-error/20 text-error rounded-xl p-xl text-center max-w-md">
          <span class="material-symbols-outlined text-4xl mb-xs">error_outline</span>
          <p>{errorMsg}</p>
        </div>
      </div>
    {:else if !currentSession}
      <div class="flex-1 flex flex-col items-center justify-center text-center border border-dashed border-outline-variant rounded-xl p-xxl">
        <span class="material-symbols-outlined text-5xl text-outline-variant mb-md">find_in_page</span>
        <h3 class="font-headline-md text-headline-md text-primary mb-xs">No Research Sessions</h3>
        <p class="font-body-reading text-body-reading text-on-surface-variant max-w-md">
          Run an autonomous web research session using the bar above to plan, gather evidence from web providers, verify claims, and generate synthesis reports.
        </p>
      </div>
    {:else}
      <!-- Active Research Brief -->
      <section class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex justify-between items-start shrink-0 shadow-[0_4px_24px_rgba(106,91,90,0.04)]">
        <div class="max-w-3xl">
          <div class="flex items-center gap-sm mb-sm flex-wrap">
            <span class="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-label-caps text-label-caps flex items-center gap-xs">
              <span class="material-symbols-outlined text-[14px]">
                {currentSession.status === 'completed' ? 'check_circle' : currentSession.status === 'failed' ? 'error' : 'psychology'}
              </span>
              Status: {currentSession.status.toUpperCase()}
            </span>
            <span class="font-status-log text-status-log text-on-surface-variant">Session: {currentSession.session_code || currentSession.id}</span>
            {#if currentSession.confidence}
              <span class="bg-surface-container-high text-on-surface-variant px-2 py-0.5 rounded font-status-log text-status-log">
                Confidence: {currentSession.confidence}%
              </span>
            {/if}
          </div>
          <h2 class="font-headline-md text-headline-md text-primary mb-xs">{currentSession.title}</h2>
          <p class="font-ui-main text-ui-main text-on-surface-variant">Query: {currentSession.query || currentSession.brief}</p>
        </div>

        {#if ['planning', 'researching', 'verifying', 'synthesizing'].includes(currentSession.status)}
          <button
            on:click={() => handleCancelSession(currentSession.id)}
            class="border border-error/30 text-error hover:bg-error/10 font-ui-medium text-ui-medium px-md py-1.5 rounded-lg flex items-center gap-xs transition-colors shrink-0"
          >
            <span class="material-symbols-outlined text-[18px]">cancel</span>
            Cancel Session
          </button>
        {/if}
      </section>

      <!-- 2-Panel Layout: Synthesized Insights & Verified Sources -->
      <div class="flex-1 flex gap-gutter overflow-hidden min-h-0">
        <!-- Live Synthesis & Findings -->
        <section class="flex-1 bg-surface-container-lowest border border-outline-variant rounded-xl shadow-[0_4px_24px_rgba(106,91,90,0.04)] flex flex-col overflow-hidden">
          <div class="p-md border-b border-outline-variant bg-surface/50 sticky top-0 z-10 flex justify-between items-center">
            <h3 class="font-label-caps text-label-caps text-on-surface-variant">Synthesized Insights & Verified Findings</h3>
            {#if currentSession.status === 'researching' || currentSession.status === 'verifying' || currentSession.status === 'synthesizing'}
              <span class="flex items-center gap-xs text-secondary font-ui-medium text-xs animate-pulse">
                <span class="material-symbols-outlined text-[16px]">sync</span>
                Engine Executing...
              </span>
            {/if}
          </div>

          <div class="p-xl overflow-y-auto flex-1 font-body-reading text-body-reading text-on-background space-y-md">
            {#if currentSession.synthesis_markdown}
              <div class="prose max-w-none space-y-sm whitespace-pre-wrap">
                {currentSession.synthesis_markdown}
              </div>
            {:else}
              <div class="text-center text-on-surface-variant/60 py-xl font-ui-main">
                <span class="material-symbols-outlined text-4xl mb-xs block">donut_large</span>
                Synthesis report will stream here as research & verification steps complete.
              </div>
            {/if}

            {#if currentSession.findings && currentSession.findings.length > 0}
              <div class="mt-lg pt-md border-t border-outline-variant/40">
                <h4 class="font-label-caps text-label-caps text-on-surface-variant mb-sm">Verified Findings Claims</h4>
                <div class="space-y-xs">
                  {#each currentSession.findings as finding}
                    <div class="p-sm rounded-lg border border-outline-variant bg-surface/40 flex items-start gap-xs">
                      <span class="material-symbols-outlined text-[18px] text-secondary shrink-0 mt-0.5">
                        {finding.is_verified ? 'verified' : 'help_outline'}
                      </span>
                      <div>
                        <p class="font-ui-main text-sm text-on-background">{finding.finding_text}</p>
                        <span class="font-status-log text-xs text-on-surface-variant/70">
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

        <!-- Verified Sources Side Panel -->
        <aside class="w-80 flex flex-col gap-md shrink-0 overflow-hidden bg-surface rounded-xl border border-outline-variant p-md">
          <div class="flex justify-between items-center pb-sm border-b border-outline-variant">
            <h3 class="font-label-caps text-label-caps text-on-surface-variant">Verified Sources</h3>
            <span class="font-status-log text-status-log text-on-surface-variant bg-surface-container-high px-2 py-1 rounded">
              {currentSession.sources ? currentSession.sources.length : 0} Sources
            </span>
          </div>

          <!-- Sessions Selector Dropdown/List -->
          {#if filteredSessions.length > 1}
            <div class="pb-xs border-b border-outline-variant/40">
              <label class="font-label-caps text-[10px] text-on-surface-variant/70 block mb-1">Switch Session</label>
              <select
                class="w-full bg-surface-container-lowest border border-outline-variant rounded p-1.5 font-ui-main text-xs text-on-background focus:outline-none"
                on:change={(e) => {
                  const sel = filteredSessions.find(s => s.id === e.currentTarget.value);
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

          <div class="overflow-y-auto flex-1 flex flex-col gap-sm">
            {#if !currentSession.sources || currentSession.sources.length === 0}
              <div class="text-center font-ui-main text-[13px] text-on-surface-variant/60 py-lg">
                No sources collected yet.
              </div>
            {:else}
              {#each currentSession.sources as source}
                <div class="p-sm rounded-lg border border-outline-variant hover:bg-surface-container-low transition-colors">
                  <div class="flex justify-between items-start mb-1">
                    <h4 class="font-ui-medium text-ui-medium text-primary text-sm line-clamp-2">{source.title}</h4>
                  </div>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="font-ui-main text-[12px] text-secondary hover:underline truncate block mb-1"
                  >
                    {source.domain || source.url}
                  </a>
                  <div class="flex justify-between items-center text-[10px] text-on-surface-variant/70">
                    <span class="bg-surface-container-high px-1.5 py-0.5 rounded uppercase font-status-log">
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
