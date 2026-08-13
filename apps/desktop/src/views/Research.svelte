<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { ResearchSession } from '$lib/api/types';

  let sessions: ResearchSession[] = [];
  let currentSession: ResearchSession | null = null;
  let isLoading = true;
  let errorMsg = '';
  let searchQuery = '';

  onMount(async () => {
    try {
      sessions = await api.getResearchSessions();
      if (sessions.length > 0) {
        currentSession = sessions[0];
      }
    } catch (err: any) {
      errorMsg = err.message || 'Failed to load research sessions';
    } finally {
      isLoading = false;
    }
  });
</script>

<div class="ml-64 flex flex-col h-screen overflow-hidden bg-background">

  <!-- TopBar -->
  <header class="bg-background flex justify-between items-center h-16 px-margin-desktop w-full z-10 sticky top-0 border-b border-outline-variant/30">
    <div class="flex items-center gap-lg">
      <h2 class="font-headline-md text-headline-md text-primary">Research Workspace</h2>
    </div>
    <div class="flex items-center gap-md">
      <div class="relative">
        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">search</span>
        <input
          bind:value={searchQuery}
          class="pl-10 pr-4 py-1.5 bg-transparent border-b-2 border-outline-variant focus:border-secondary focus:outline-none font-ui-main text-ui-main text-on-background placeholder:text-outline w-64 transition-colors"
          placeholder="Search research sessions..."
          type="text"
        />
      </div>
    </div>
  </header>

  <!-- Workspace -->
  <main class="flex-1 overflow-hidden flex flex-col p-margin-desktop pt-lg gap-lg">
    {#if isLoading}
      <div class="flex-1 flex items-center justify-center font-ui-main text-on-surface-variant animate-pulse">
        Loading research sessions from backend...
      </div>
    {:else if errorMsg}
      <div class="flex-1 flex items-center justify-center">
        <div class="bg-error/10 border border-error/20 text-error rounded-xl p-xl text-center">
          {errorMsg}
        </div>
      </div>
    {:else if !currentSession}
      <div class="flex-1 flex flex-col items-center justify-center text-center border border-dashed border-outline-variant rounded-xl p-xxl">
        <span class="material-symbols-outlined text-5xl text-outline-variant mb-md">find_in_page</span>
        <h3 class="font-headline-md text-headline-md text-primary mb-xs">No Research Sessions</h3>
        <p class="font-body-reading text-body-reading text-on-surface-variant max-w-md">
          Run a research task from the Home workspace to trigger autonomous web research, synthesis, and source verification.
        </p>
      </div>
    {:else}
      <!-- Research Brief -->
      <section class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex justify-between items-start shrink-0 shadow-[0_4px_24px_rgba(106,91,90,0.04)]">
        <div class="max-w-3xl">
          <div class="flex items-center gap-sm mb-sm">
            <span class="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-label-caps text-label-caps flex items-center gap-xs">
              <span class="material-symbols-outlined text-[14px]">psychology</span>
              {currentSession.status}
            </span>
            <span class="font-status-log text-status-log text-on-surface-variant">Session: {currentSession.id}</span>
          </div>
          <h2 class="font-headline-md text-headline-md text-primary mb-xs">{currentSession.title}</h2>
          <p class="font-ui-main text-ui-main text-on-surface-variant">Query: {currentSession.query}</p>
        </div>
      </section>

      <!-- 2-panel layout -->
      <div class="flex-1 flex gap-gutter overflow-hidden min-h-0">
        <!-- Live Synthesis -->
        <section class="flex-1 bg-surface-container-lowest border border-outline-variant rounded-xl shadow-[0_4px_24px_rgba(106,91,90,0.04)] flex flex-col overflow-hidden">
          <div class="p-md border-b border-outline-variant bg-surface/50 sticky top-0 z-10">
            <h3 class="font-label-caps text-label-caps text-on-surface-variant">Synthesized Insights</h3>
          </div>
          <div class="p-xl overflow-y-auto flex-1 font-body-reading text-body-reading text-on-background">
            <p>{currentSession.summary || 'Synthesis will appear as research steps complete.'}</p>
          </div>
        </section>

        <!-- Sources -->
        <aside class="w-80 flex flex-col gap-md shrink-0 overflow-hidden bg-surface rounded-xl border border-outline-variant p-md">
          <div class="flex justify-between items-center mb-xs pb-sm border-b border-outline-variant">
            <h3 class="font-label-caps text-label-caps text-on-surface-variant">Verified Sources</h3>
            <span class="font-status-log text-status-log text-on-surface-variant bg-surface-container-high px-2 py-1 rounded">
              {currentSession.sources ? currentSession.sources.length : 0} Sources
            </span>
          </div>
          <div class="overflow-y-auto flex-1 flex flex-col gap-sm">
            {#if !currentSession.sources || currentSession.sources.length === 0}
              <div class="text-center font-ui-main text-[13px] text-on-surface-variant/60 py-lg">
                No sources collected yet.
              </div>
            {:else}
              {#each currentSession.sources as source}
                <div class="p-sm rounded-lg border border-outline-variant hover:bg-surface-container-low transition-colors">
                  <h4 class="font-ui-medium text-ui-medium text-primary text-sm mb-1">{source.title}</h4>
                  <a href={source.url} target="_blank" class="font-ui-main text-[12px] text-secondary hover:underline truncate block">{source.url}</a>
                </div>
              {/each}
            {/if}
          </div>
        </aside>
      </div>
    {/if}
  </main>
</div>
