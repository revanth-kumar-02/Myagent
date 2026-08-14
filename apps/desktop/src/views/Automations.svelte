<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Automation } from '$lib/api/types';

  let automations: Automation[] = [];
  let isLoading = true;
  let errorMsg = '';

  onMount(async () => {
    try {
      automations = await api.getAutomations();
    } catch (err: any) {
      errorMsg = err.message || 'Failed to load automations';
    } finally {
      isLoading = false;
    }
  });
</script>

<main class="ml-56 pt-12 px-6 pb-6 min-h-[calc(100vh-48px)] bg-background flex flex-col flex-1">
  <div class="w-full max-w-6xl flex-1 flex flex-col min-h-0 pt-2 pb-4">

    <header class="mb-4 flex justify-between items-end border-b border-outline-variant/40 pb-3 shrink-0">
      <div>
        <h2 class="font-headline-md text-[18px] text-primary font-semibold mb-0.5">Automations</h2>
        <p class="font-ui-main text-[13px] text-on-surface-variant">
          Scheduled agent workflows and system triggers.
        </p>
      </div>
      <button class="bg-primary text-on-primary hover:bg-primary-container px-3 py-1.5 rounded-md font-ui-medium text-[12px] flex items-center gap-1 transition-colors shadow-sm h-8">
        <span class="material-symbols-outlined text-[16px]">add</span>
        New Workflow
      </button>
    </header>

    {#if isLoading}
      <div class="flex-1 flex items-center justify-center font-ui-main text-[13px] text-on-surface-variant animate-pulse">
        Loading workflows...
      </div>
    {:else if errorMsg}
      <div class="bg-error/10 border border-error/20 text-error rounded-md p-3 font-ui-main text-[13px] text-center">
        {errorMsg}
      </div>
    {:else if automations.length === 0}
      <div class="flex-1 flex flex-col items-center justify-center py-12 text-center border border-dashed border-outline-variant/60 rounded-md p-8">
        <span class="material-symbols-outlined text-4xl text-outline-variant mb-2">account_tree</span>
        <h3 class="font-headline-md text-[18px] text-primary mb-1 font-semibold">No Automations Configured</h3>
        <p class="font-ui-main text-[13px] text-on-surface-variant max-w-md">
          Create scheduled workflows to periodically trigger agent checks, research summaries, and filesystem organization.
        </p>
      </div>
    {:else}
      <div class="flex-1 overflow-y-auto space-y-3 pr-1">
        {#each automations as auto}
          <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3.5 shadow-sm">
            <div class="flex justify-between items-start mb-2">
              <div>
                <h3 class="font-ui-medium text-[14px] text-primary font-medium">{auto.name}</h3>
                <p class="font-ui-main text-[12px] text-on-surface-variant mt-0.5">{auto.description}</p>
              </div>
              <span class="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded-full font-label-caps text-[10px] flex items-center gap-1">
                <span class="material-symbols-outlined text-[12px]">play_arrow</span> {auto.is_active ? 'Active' : 'Paused'}
              </span>
            </div>
            {#if auto.last_run}
              <div class="font-status-log text-[11px] text-on-surface-variant pt-2 border-t border-outline-variant/40">
                Last Run: <span class="text-primary">{auto.last_run}</span>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

  </div>
</main>
