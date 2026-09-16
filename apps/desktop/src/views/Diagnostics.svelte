<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { SystemHealth, DiagnosticsInfo } from '$lib/api/types';

  let health: SystemHealth | null = null;
  let diagnostics: DiagnosticsInfo | null = null;
  let isLoading = true;
  let isRefreshing = false;
  let errorMsg = '';

  onMount(async () => {
    await fetchDiagnosticsData();
  });

  async function fetchDiagnosticsData() {
    isRefreshing = true;
    errorMsg = '';
    try {
      const [hData, dData] = await Promise.all([
        api.getReadiness().catch(() => null),
        api.getDiagnostics().catch(() => null),
      ]);
      health = hData;
      diagnostics = dData;
    } catch (err: any) {
      errorMsg = err.message || 'Failed to fetch diagnostic telemetry';
    } finally {
      isLoading = false;
      isRefreshing = false;
    }
  }

  function getStatusBadge(statusStr?: string) {
    const norm = (statusStr || 'unknown').toLowerCase();
    if (norm === 'healthy' || norm === 'connected' || norm === 'available' || norm === 'active' || norm === 'running' || norm === 'ready') {
      return { label: 'HEALTHY', bg: 'bg-[#1b4332] border border-[#2d6a4f] text-[#d8f3dc]', dot: 'bg-[#52b788]' };
    }
    if (norm === 'degraded' || norm === 'idle') {
      return { label: 'DEGRADED', bg: 'bg-[#533f03] border border-[#997404] text-[#fff3cd]', dot: 'bg-[#ffc107]' };
    }
    if (norm === 'not_configured' || norm === 'not configured') {
      return { label: 'NOT CONFIGURED', bg: 'bg-[#4a3e3d] border border-[#695856] text-[#f3dedc]', dot: 'bg-[#a18f8e]' };
    }
    return { label: 'UNAVAILABLE', bg: 'bg-[#5c1d24] border border-[#842029] text-[#f8d7da]', dot: 'bg-[#ea868f]' };
  }
</script>

<main class="ml-56 pt-12 min-h-[calc(100vh-48px)] w-[calc(100vw-14rem)] bg-background flex flex-col items-center select-none overflow-y-auto px-6 py-8 animate-page-enter">
  <div class="w-full max-w-[950px] mx-auto space-y-8">
    
    <!-- Top Action Bar -->
    <div class="flex items-center justify-between border-b border-outline-variant/40 pb-4">
      <div>
        <h1 class="font-headline-md text-[22px] text-primary font-semibold tracking-tight">System Health & Diagnostics</h1>
        <p class="font-ui-main text-[13px] text-on-surface-variant/70 mt-1">Real-time telemetry and infrastructure monitoring for Cocoa Agent.</p>
      </div>

      <button
        onclick={fetchDiagnosticsData}
        disabled={isRefreshing}
        class="btn-primary disabled:opacity-50"
      >
        <span class="material-symbols-outlined text-[16px] text-white {isRefreshing ? 'animate-spin' : ''}">refresh</span>
        {isRefreshing ? 'Refreshing...' : 'REFRESH STATUS'}
      </button>
    </div>

    {#if errorMsg}
      <div class="p-3.5 rounded-md bg-rose-950/30 border border-rose-800/40 text-rose-300 font-ui-main text-[12px] flex items-center gap-2">
        <span class="material-symbols-outlined text-[16px]">warning</span>
        {errorMsg}
      </div>
    {/if}

    <!-- SYSTEM HEALTH PANEL -->
    <section class="space-y-3">
      <div class="flex items-center gap-2">
        <span class="material-symbols-outlined text-[18px] text-secondary">monitor_heart</span>
        <h2 class="font-label-caps text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold">System Health Matrix</h2>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {#if health}
          {#each [
            { name: 'PostgreSQL Database', val: health.database },
            { name: 'Native pgvector', val: health.pgvector },
            { name: 'Groq LLM Engine', val: health.groq },
            { name: 'Tavily Search Engine', val: health.tavily },
            { name: 'Brave Search Fallback', val: health.brave },
            { name: 'Playwright Browser', val: health.playwright },
            { name: 'Automation Scheduler', val: health.scheduler },
            { name: 'WebSocket Event Stream', val: health.websocket },
            { name: 'Tool Registry', val: health.tool_registry },
            { name: 'Permission Manager', val: health.permission_manager }
          ] as item}
            {@const badge = getStatusBadge(item.val)}
            <div class="bg-surface border border-outline-variant/60 rounded-lg p-3.5 flex items-center justify-between hover:bg-surface-container-lowest transition-colors shadow-2xs">
              <div class="space-y-0.5">
                <span class="font-ui-medium text-[13px] text-primary block">{item.name}</span>
                <span class="font-status-log text-[10px] text-on-surface-variant/60 capitalize">{item.val}</span>
              </div>
              <div class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-label-caps font-semibold uppercase tracking-wider {badge.bg}">
                <span class="w-1.5 h-1.5 rounded-full {badge.dot}"></span>
                {badge.label}
              </div>
            </div>
          {/each}
        {:else if isLoading}
          <div class="col-span-full p-8 text-center text-on-surface-variant/60 font-ui-main text-[13px] bg-surface border border-outline-variant/40 rounded-lg">
            Loading system health telemetry...
          </div>
        {/if}
      </div>
    </section>

    <!-- DIAGNOSTICS VIEW -->
    <section class="space-y-3 pt-2 border-t border-outline-variant/40">
      <div class="flex items-center gap-2">
        <span class="material-symbols-outlined text-[18px] text-secondary">terminal</span>
        <h2 class="font-label-caps text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold">Runtime Diagnostics</h2>
      </div>

      {#if diagnostics}
        <div class="bg-surface border border-outline-variant/60 rounded-lg divide-y divide-outline-variant/40 overflow-hidden shadow-2xs">
          {#each [
            { label: 'Cocoa Version', value: diagnostics.cocoa_version },
            { label: 'Python Environment', value: diagnostics.python_version },
            { label: 'Active Database Backend', value: diagnostics.database_backend },
            { label: 'PostgreSQL Server', value: diagnostics.postgres_version },
            { label: 'pgvector Extension', value: diagnostics.pgvector_version },
            { label: 'Active LLM Model', value: diagnostics.active_llm },
            { label: 'Active Research Engine', value: diagnostics.active_research_provider },
            { label: 'Browser Automation Runtime', value: diagnostics.browser_runtime },
            { label: 'Automation Scheduler State', value: diagnostics.scheduler_status },
            { label: 'Tool Registry', value: diagnostics.tool_registry },
            { label: 'Permission Boundary Manager', value: diagnostics.permission_manager }
          ] as diag}
            <div class="px-4 py-3 flex items-center justify-between hover:bg-surface-container-lowest transition-colors">
              <span class="font-ui-medium text-[12px] text-on-surface-variant">{diag.label}</span>
              <span class="font-status-log text-[12px] text-primary font-mono bg-surface-container-high px-2 py-0.5 rounded border border-outline-variant/40">{diag.value}</span>
            </div>
          {/each}
        </div>
      {:else if isLoading}
        <div class="p-8 text-center text-on-surface-variant/60 font-ui-main text-[13px] bg-surface border border-outline-variant/40 rounded-lg">
          Loading diagnostic details...
        </div>
      {/if}
    </section>

  </div>
</main>
