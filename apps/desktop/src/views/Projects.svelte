<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Project } from '$lib/api/types';

  let projects: Project[] = [];
  let isLoading = true;
  let errorMsg = '';

  onMount(async () => {
    try {
      projects = await api.getProjects();
    } catch (err: any) {
      errorMsg = err.message || 'Failed to load projects';
    } finally {
      isLoading = false;
    }
  });
</script>

<main class="ml-64 pt-24 px-margin-desktop pb-xxl">
  <div class="max-w-[900px]">
    <div class="mb-xl">
      <h2 class="font-label-caps text-label-caps text-on-surface-variant mb-xs">YOUR WORKSPACE</h2>
      <h1 class="font-display-lg text-display-lg text-primary">Projects</h1>
    </div>

    {#if isLoading}
      <div class="py-xxl text-center font-ui-main text-on-surface-variant animate-pulse">
        Loading projects from database...
      </div>
    {:else if errorMsg}
      <div class="bg-error/10 border border-error/20 text-error rounded-xl p-lg font-ui-main">
        {errorMsg}
      </div>
    {:else if projects.length === 0}
      <!-- Empty state -->
      <div class="flex flex-col items-center justify-center py-xxl text-center border border-dashed border-outline-variant rounded-xl">
        <span class="material-symbols-outlined text-5xl text-outline-variant mb-lg">folder_open</span>
        <h3 class="font-headline-md text-headline-md text-on-surface mb-sm">No projects yet</h3>
        <p class="font-ui-main text-ui-main text-on-surface-variant mb-xl max-w-sm">
          Projects are persistent workspaces containing tasks, research, files, and decisions.
        </p>
        <button class="bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary-container px-lg py-sm rounded-full font-ui-medium text-ui-medium flex items-center gap-xs transition-colors shadow-sm">
          <span class="material-symbols-outlined text-[18px]">add</span>
          New Project
        </button>
      </div>
    {:else}
      <div class="grid grid-cols-2 gap-lg">
        {#each projects as project}
          <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg hover:border-outline transition-colors shadow-sm">
            <div class="flex items-center gap-md mb-sm">
              <span class="material-symbols-outlined text-primary text-2xl">folder_open</span>
              <h3 class="font-ui-medium text-ui-medium text-primary">{project.title}</h3>
            </div>
            <p class="font-ui-main text-[13px] text-on-surface-variant">{project.description || 'No description provided.'}</p>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</main>
