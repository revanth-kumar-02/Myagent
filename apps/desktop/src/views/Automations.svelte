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

<main class="ml-64 pt-16 min-h-screen bg-background">
  <div class="px-margin-desktop pt-lg max-w-4xl mx-auto pb-xxl">

    <header class="mb-xl flex justify-between items-end border-b border-outline-variant pb-lg">
      <div>
        <h2 class="font-display-lg text-display-lg text-primary mb-2">Automations</h2>
        <p class="font-ui-main text-ui-main text-on-surface-variant">
          Scheduled agent workflows and system triggers.
        </p>
      </div>
      <button class="bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary-container px-lg py-sm rounded-full font-ui-medium text-ui-medium flex items-center gap-xs transition-colors shadow-sm">
        <span class="material-symbols-outlined text-[18px]">add</span>
        New Workflow
      </button>
    </header>

    {#if isLoading}
      <div class="py-xxl text-center font-ui-main text-on-surface-variant animate-pulse">
        Loading workflows...
      </div>
    {:else if errorMsg}
      <div class="bg-error/10 border border-error/20 text-error rounded-xl p-lg font-ui-main text-center">
        {errorMsg}
      </div>
    {:else if automations.length === 0}
      <div class="flex flex-col items-center justify-center py-xxl text-center border border-dashed border-outline-variant rounded-xl p-xxl">
        <span class="material-symbols-outlined text-5xl text-outline-variant mb-md">account_tree</span>
        <h3 class="font-headline-md text-headline-md text-primary mb-xs">No Automations Configured</h3>
        <p class="font-body-reading text-body-reading text-on-surface-variant max-w-md">
          Create scheduled workflows to periodically trigger agent checks, research summaries, and filesystem organization.
        </p>
      </div>
    {:else}
      <div class="space-y-lg">
        {#each automations as auto}
          <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg shadow-sm">
            <div class="flex justify-between items-start mb-md">
              <div>
                <h3 class="font-headline-md text-headline-md text-primary">{auto.name}</h3>
                <p class="font-ui-main text-ui-main text-on-surface-variant">{auto.description}</p>
              </div>
              <span class="bg-secondary-container text-on-secondary-container px-3 py-1 rounded-full font-label-caps text-label-caps flex items-center gap-1">
                <span class="material-symbols-outlined text-[14px]">play_arrow</span> {auto.is_active ? 'Active' : 'Paused'}
              </span>
            </div>
            {#if auto.last_run}
              <div class="font-status-log text-status-log text-on-surface-variant pt-sm border-t border-outline-variant">
                Last Run: <span class="text-primary">{auto.last_run}</span>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

  </div>
</main>
