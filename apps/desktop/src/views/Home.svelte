<script lang="ts">
  import { onMount } from 'svelte';
  import StatusChip from '$lib/components/StatusChip.svelte';
  import { api } from '$lib/api/client';
  import type { Task, Project } from '$lib/api/types';
  import { navigate } from '$lib/stores/navigation';
  import { userProfile, loadUserProfile } from '$lib/stores/profile';

  let commandText = '';
  let isSubmitting = false;
  let submitError = '';

  let tasks: Task[] = [];
  let projects: Project[] = [];
  let selectedProjectId: string = '';

  const quickActions = [
    { label: 'Research', icon: 'travel_explore', prompt: 'Research alternatives and best practices for ' },
    { label: 'Work with files', icon: 'folder_open', prompt: 'Inspect and organize files in current workspace' },
    { label: 'Analyze a project', icon: 'analytics', prompt: 'Analyze architecture and dependencies for ' },
    { label: 'Automate something', icon: 'auto_mode', prompt: 'Create an automated workflow for ' }
  ];

  function getGreetingPrefix(): string {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return 'Good morning';
    } else if (hour >= 12 && hour < 17) {
      return 'Good afternoon';
    } else {
      return 'Good evening';
    }
  }

  onMount(async () => {
    await Promise.all([
      loadUserProfile(),
      loadHomeData()
    ]);
  });

  async function loadHomeData() {
    try {
      const [tData, pData] = await Promise.all([
        api.getTasks().catch(() => []),
        api.getProjects().catch(() => []),
      ]);
      tasks = tData;
      projects = pData;
      if (pData.length > 0 && !selectedProjectId) {
        selectedProjectId = pData[0].id;
      }
    } catch {
      // ignore errors
    }
  }

  async function handleRunGoal() {
    if (!commandText.trim() || isSubmitting) return;
    isSubmitting = true;
    submitError = '';

    try {
      await api.runAgent(commandText.trim(), selectedProjectId || undefined);
      commandText = '';
      navigate('tasks');
    } catch (err: any) {
      submitError = err.message || 'Failed to trigger agent execution';
    } finally {
      isSubmitting = false;
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleRunGoal();
    }
  }

  function handleQuickAction(promptText: string) {
    commandText = promptText;
    const textarea = document.getElementById('cocoa-composer-textarea') as HTMLTextAreaElement;
    if (textarea) {
      textarea.focus();
      textarea.setSelectionRange(promptText.length, promptText.length);
    }
  }

  function autoResize(event: Event) {
    const el = event.target as HTMLTextAreaElement;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  }

  $: activeTasks = tasks.filter((t) => t.status === 'planning' || t.status === 'executing' || t.status === 'observing' || t.status === 'verifying');
  $: hasRealUsername = Boolean($userProfile.username && $userProfile.username.trim() && $userProfile.username.toLowerCase() !== 'user');
</script>

<main class="ml-56 pt-12 min-h-[calc(100vh-48px)] w-[calc(100vw-14rem)] bg-background flex flex-col items-center select-none overflow-y-auto">
  <!-- Centered Content Column (width: calc(100% - 48px); max-width: 900px; margin-inline: auto) -->
  <div class="w-[calc(100%-48px)] max-w-[900px] mx-auto flex flex-col items-center pt-[12vh] pb-12">

    <!-- Cocoa Identity / Status Badge -->
    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-high border border-outline-variant/40 mb-4 mx-auto">
      <span class="w-1.5 h-1.5 rounded-full bg-secondary"></span>
      <span class="font-label-caps text-[10px] text-on-surface-variant/80 tracking-widest uppercase font-semibold">
        COCOA AGENT · READY
      </span>
    </div>

    <!-- Centered Welcome Header -->
    <header class="text-center mb-7 w-full max-w-[800px] mx-auto">
      {#if hasRealUsername}
        <h1 class="font-headline-md text-[26px] text-primary font-semibold tracking-tight leading-snug">
          {getGreetingPrefix()}, {$userProfile.username}.
        </h1>
        <h2 class="font-headline-md text-[26px] text-primary font-semibold tracking-tight leading-snug mt-1">
          What’s on your agenda today?
        </h2>
      {:else}
        <h1 class="font-headline-md text-[26px] text-primary font-semibold tracking-tight leading-snug">
          What’s on your agenda today?
        </h1>
      {/if}

      <p class="font-ui-main text-[13px] text-on-surface-variant/80 mt-2.5 leading-relaxed max-w-lg mx-auto">
        Research something, work with your files, or let Cocoa take care of a task.
      </p>
    </header>

    <!-- Centered Agent Composer (Primary Interaction Surface - max 900px) -->
    <section class="w-full max-w-[900px] text-left">
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-xl p-5 shadow-sm focus-within:border-secondary focus-within:ring-1 focus-within:ring-secondary/20 transition-all duration-200 min-h-[160px] flex flex-col justify-between">
        
        <textarea
          id="cocoa-composer-textarea"
          bind:value={commandText}
          oninput={autoResize}
          onkeydown={handleKeydown}
          placeholder="What can Cocoa help you accomplish?"
          rows={3}
          class="w-full bg-transparent border-none outline-none font-ui-main text-[14px] leading-[22px] text-primary placeholder:text-on-surface-variant/50 resize-none focus:ring-0 text-left"
        ></textarea>

        {#if submitError}
          <div class="mt-2 text-error font-ui-main text-[12px] flex items-center gap-1">
            <span class="material-symbols-outlined text-[14px]">error</span>
            {submitError}
          </div>
        {/if}

        <div class="mt-4 flex items-center justify-between border-t border-outline-variant/40 pt-3.5">
          <div class="flex items-center gap-2.5">
            <button class="flex items-center gap-1.5 text-on-surface-variant hover:text-primary hover:bg-surface-container-low px-3 py-1.5 rounded-md transition-colors font-ui-medium text-[12px]">
              <span class="material-symbols-outlined text-[16px]">attach_file</span>
              + File
            </button>

            {#if projects.length > 0}
              <div class="relative inline-block">
                <select
                  bind:value={selectedProjectId}
                  class="appearance-none bg-surface-container-low border border-outline-variant/50 hover:border-outline text-on-surface-variant pl-7 pr-7 py-1.5 rounded-full font-label-caps text-[11px] focus:outline-none transition-colors cursor-pointer"
                >
                  {#each projects as proj}
                    <option value={proj.id}>Project: {proj.title}</option>
                  {/each}
                </select>
                <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[14px] text-on-surface-variant pointer-events-none">folder_open</span>
                <span class="material-symbols-outlined absolute right-2 top-1/2 -translate-y-1/2 text-[14px] text-on-surface-variant pointer-events-none">arrow_drop_down</span>
              </div>
            {:else}
              <span class="flex items-center gap-1.5 text-on-surface-variant border border-outline-variant/50 px-3 py-1 rounded-full font-label-caps text-[11px] opacity-70">
                <span class="material-symbols-outlined text-[14px]">folder_open</span>
                Global Workspace
              </span>
            {/if}
          </div>

          <div class="flex items-center gap-3">
            <span class="hidden sm:inline font-status-log text-[10px] text-on-surface-variant/60">⌘↵ Run</span>
            <button
              onclick={handleRunGoal}
              disabled={isSubmitting || !commandText.trim()}
              class="bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary-container disabled:opacity-50 px-4 py-1.5 rounded-full font-ui-medium text-[12px] flex items-center gap-1.5 transition-colors shadow-sm group"
            >
              {isSubmitting ? 'Planning...' : 'Run'}
              <span class="material-symbols-outlined text-[16px] group-hover:translate-x-0.5 transition-transform">arrow_forward</span>
            </button>
          </div>
        </div>

      </div>
    </section>

    <!-- Centered Quick Action Suggestion Chips -->
    <div class="mt-4 flex flex-wrap items-center justify-center gap-2.5 w-full max-w-[900px] select-none">
      {#each quickActions as action}
        <button
          onclick={() => handleQuickAction(action.prompt)}
          class="bg-surface border border-outline-variant/60 hover:bg-surface-container hover:border-outline-variant px-3.5 py-1.5 rounded-full font-ui-medium text-[12px] text-on-surface-variant flex items-center gap-1.5 transition-all cursor-pointer shadow-xs group"
        >
          <span class="material-symbols-outlined text-[15px] text-secondary group-hover:scale-110 transition-transform">{action.icon}</span>
          <span>{action.label}</span>
        </button>
      {/each}
    </div>

    <!-- Active Work (Centered 900px column) -->
    {#if activeTasks.length > 0}
      <section class="mt-9 w-full max-w-[900px] text-left">
        <div class="flex items-center justify-between mb-2.5">
          <h2 class="font-label-caps text-[10px] text-on-surface-variant/80 uppercase tracking-wider font-semibold">ACTIVE WORK</h2>
          <button onclick={() => navigate('tasks')} class="font-ui-medium text-[11px] text-secondary hover:underline">View all</button>
        </div>
        <div class="space-y-2">
          {#each activeTasks as task}
            <div
              onclick={() => navigate('tasks')}
              onkeydown={(e) => e.key === 'Enter' && navigate('tasks')}
              role="button"
              tabindex={0}
              class="bg-surface border border-outline-variant/60 rounded-md p-3 flex items-center justify-between hover:bg-surface-container-lowest transition-colors cursor-pointer group"
            >
              <div class="flex items-center gap-3">
                <span class="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                <div>
                  <h3 class="font-ui-medium text-[13px] text-primary leading-tight">{task.title}</h3>
                  <p class="font-ui-main text-[11px] text-on-surface-variant/70 mt-0.5">{task.description || 'Goal in progress'}</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <StatusChip status={task.status} />
                <span class="material-symbols-outlined text-[16px] text-on-surface-variant/60 group-hover:translate-x-0.5 transition-transform">arrow_forward</span>
              </div>
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <!-- Recent Work (Centered 900px column) -->
    {#if projects.length > 0}
      <section class="mt-7 w-full max-w-[900px] text-left">
        <div class="flex items-center justify-between mb-2.5">
          <h2 class="font-label-caps text-[10px] text-on-surface-variant/80 uppercase tracking-wider font-semibold">RECENT WORK</h2>
          <button onclick={() => navigate('projects')} class="font-ui-medium text-[11px] text-secondary hover:underline">View all</button>
        </div>
        <div class="bg-surface border border-outline-variant/60 rounded-md divide-y divide-outline-variant/40 overflow-hidden">
          {#each projects.slice(0, 4) as project}
            <div
              onclick={() => navigate('projects')}
              onkeydown={(e) => e.key === 'Enter' && navigate('projects')}
              role="button"
              tabindex={0}
              class="p-3 px-3.5 flex items-center justify-between hover:bg-surface-container-lowest transition-colors cursor-pointer group"
            >
              <div class="flex items-center gap-3">
                <span class="material-symbols-outlined text-[16px] text-secondary">folder_open</span>
                <span class="font-ui-medium text-[12px] text-primary truncate max-w-md">{project.title}</span>
              </div>
              <span class="font-status-log text-[10px] text-on-surface-variant/60 opacity-80">Project</span>
            </div>
          {/each}
        </div>
      </section>
    {/if}

  </div>
</main>
