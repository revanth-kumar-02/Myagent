<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Task, TaskStep, ActivityLog } from '$lib/api/types';

  let activeTask: Task | null = null;
  let steps: TaskStep[] = [];
  let activities: ActivityLog[] = [];
  let isLoading = true;
  let errorMsg = '';
  let unsubscribeWs: (() => void) | null = null;

  onMount(async () => {
    await loadTaskWorkspace();

    // Subscribe to live WebSocket events
    unsubscribeWs = api.connectWebSocket((evt: any) => {
      handleWsEvent(evt);
    });
  });

  onDestroy(() => {
    if (unsubscribeWs) unsubscribeWs();
  });

  async function loadTaskWorkspace() {
    isLoading = true;
    errorMsg = '';
    try {
      const allTasks = await api.getTasks();
      if (allTasks.length > 0) {
        // Pick active or latest task
        activeTask = allTasks.find(t => t.status === 'executing' || t.status === 'planning' || t.status === 'verifying') || allTasks[0];
        
        if (activeTask) {
          const [stepData, actData] = await Promise.all([
            api.getTaskSteps(activeTask.id).catch(() => []),
            api.getTaskActivity(activeTask.id).catch(() => []),
          ]);
          steps = stepData;
          activities = actData;
        }
      } else {
        activeTask = null;
        steps = [];
        activities = [];
      }
    } catch (err: any) {
      errorMsg = err.message || 'Failed to load task workspace';
    } finally {
      isLoading = false;
    }
  }

  function handleWsEvent(evt: any) {
    if (!evt || !evt.event) return;

    const timestamp = new Date().toLocaleTimeString();

    if (evt.task_id && activeTask && evt.task_id === activeTask.id) {
      if (evt.status) activeTask.status = evt.status;
      if (evt.result) activeTask.result = evt.result;
    }

    // Append event to live terminal activity list
    activities = [
      {
        id: `act_${Date.now()}_${Math.random()}`,
        task_id: evt.task_id || activeTask?.id || '',
        event_type: evt.event,
        message: evt.message || `Event: ${evt.event}`,
        details: evt.details || null,
        timestamp,
      },
      ...activities,
    ];

    // Refresh steps if step event
    if (evt.event.includes('step') || evt.event.includes('plan')) {
      if (activeTask) {
        api.getTaskSteps(activeTask.id).then(s => steps = s).catch(() => {});
      }
    }
  }
</script>

<!-- Full-viewport layout offset by sidebar + topbar -->
<main class="ml-64 pt-16 px-margin-desktop pb-margin-desktop h-screen overflow-hidden flex flex-col">

  <!-- Header row -->
  <div class="flex justify-between items-end py-md mb-lg border-b border-outline-variant shrink-0">
    <div>
      <p class="font-label-caps text-label-caps text-on-surface-variant mb-xs">Active Task Workspace</p>
      <h2 class="font-display-lg text-display-lg text-primary truncate max-w-4xl">
        {activeTask ? activeTask.title : isLoading ? 'Loading workspace...' : 'No active task selected'}
      </h2>
    </div>
    {#if activeTask}
      <div class="flex items-center gap-sm bg-secondary-container/20 px-md py-sm rounded-full border border-secondary/20 shadow-[0_0_24px_rgba(119,87,81,0.05)] shrink-0 ml-lg">
        <span class="w-2 h-2 rounded-full bg-secondary {activeTask.status === 'executing' || activeTask.status === 'planning' ? 'animate-pulse' : ''}"></span>
        <span class="font-label-caps text-label-caps text-secondary uppercase">{activeTask.status}</span>
      </div>
    {/if}
  </div>

  {#if isLoading}
    <div class="flex-1 flex items-center justify-center font-ui-main text-on-surface-variant animate-pulse">
      Connecting to agent backend...
    </div>
  {:else if errorMsg}
    <div class="flex-1 flex items-center justify-center">
      <div class="bg-error/10 border border-error/20 text-error rounded-lg p-xl text-center max-w-md">
        <span class="material-symbols-outlined text-3xl mb-xs">warning</span>
        <p class="font-ui-medium text-ui-medium">{errorMsg}</p>
      </div>
    </div>
  {:else if !activeTask}
    <div class="flex-1 flex items-center justify-center">
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xxl text-center max-w-lg">
        <span class="material-symbols-outlined text-4xl text-on-surface-variant mb-md">checklist</span>
        <h3 class="font-headline-md text-headline-md text-primary mb-xs">No Active Agent Tasks</h3>
        <p class="font-body-reading text-body-reading text-on-surface-variant mb-lg">
          Start a new task from the Home command composer to watch the Agent Core plan, execute tools, and verify results live.
        </p>
      </div>
    </div>
  {:else}
    <!-- 3-column workspace -->
    <div class="grid grid-cols-12 gap-gutter flex-1 overflow-hidden min-h-0">

      <!-- Column 1: PLAN -->
      <section class="col-span-3 flex flex-col overflow-hidden">
        <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md flex items-center gap-sm shrink-0">
          <span class="material-symbols-outlined text-sm">flag</span>
          PLAN ({steps.length} STEPS)
        </h3>
        <div class="bg-surface-container-lowest rounded-lg border border-outline-variant p-md flex-1 overflow-y-auto shadow-[0_4px_24px_rgba(106,91,90,0.04)]">
          {#if steps.length === 0}
            <div class="text-center text-on-surface-variant/60 font-ui-main text-[13px] py-xl">
              Generating plan steps...
            </div>
          {:else}
            <ul class="space-y-sm">
              {#each steps as step}
                <li class="flex items-start gap-sm p-sm rounded transition-colors group
                  {step.status === 'executing' ? 'bg-surface-container-low border-l-2 border-secondary relative overflow-hidden' : 'hover:bg-surface-container-low'}">
                  {#if step.status === 'executing'}
                    <div class="absolute inset-0 bg-gradient-to-r from-secondary/5 to-transparent pointer-events-none"></div>
                  {/if}
                  {#if step.status === 'completed'}
                    <span class="material-symbols-outlined text-secondary-fixed-dim shrink-0 mt-xs">check_circle</span>
                    <span class="font-ui-main text-ui-main text-on-surface-variant line-through opacity-70">{step.title}</span>
                  {:else if step.status === 'executing'}
                    <span class="material-symbols-outlined text-secondary shrink-0 mt-xs relative z-10 animate-spin">sync</span>
                    <span class="font-ui-medium text-ui-medium text-primary relative z-10">{step.title}</span>
                  {:else}
                    <span class="material-symbols-outlined text-outline shrink-0 mt-xs">radio_button_unchecked</span>
                    <span class="font-ui-main text-ui-main text-on-surface">{step.title}</span>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </section>

      <!-- Column 2: ACTIVITY (dark cocoa terminal) -->
      <section class="col-span-5 flex flex-col overflow-hidden pl-md border-l border-outline-variant/50">
        <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md flex items-center gap-sm shrink-0">
          <span class="material-symbols-outlined text-sm">history</span>
          LIVE ACTIVITY
        </h3>
        <div class="bg-[#352928] rounded-lg p-md flex-1 overflow-y-auto shadow-inner border border-[#1f1514]/20 relative">
          <div class="absolute top-0 right-0 p-sm opacity-30">
            <span class="material-symbols-outlined text-on-primary-container text-2xl">terminal</span>
          </div>
          <div class="space-y-3 font-status-log text-status-log text-[#a18f8e]">
            {#if activities.length === 0}
              <div class="text-[#a18f8e]/50 py-md text-[13px]">
                Waiting for agent events...
              </div>
            {:else}
              {#each activities as entry}
                <div class="flex gap-md items-start">
                  <span class="text-[#e7bdb6] shrink-0 opacity-70">[{entry.timestamp}]</span>
                  <div>
                    <span class="text-[#f3dedc] mr-sm">›</span>
                    <span class="text-[#ffffff] font-medium">{entry.message}</span>
                    {#if entry.details}
                      <pre class="mt-xs text-[11px] opacity-70 font-mono text-[#ffdad4] whitespace-pre-wrap">{JSON.stringify(entry.details, null, 2)}</pre>
                    {/if}
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      </section>

      <!-- Column 3: RESULT -->
      <section class="col-span-4 flex flex-col overflow-hidden pl-md border-l border-outline-variant/50">
        <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md flex items-center gap-sm shrink-0">
          <span class="material-symbols-outlined text-sm">article</span>
          VERIFIED RESULT
        </h3>
        <div class="bg-surface-container-lowest rounded-lg border border-outline-variant p-xl flex-1 flex flex-col items-center justify-center text-center shadow-[0_4px_24px_rgba(106,91,90,0.04)] relative overflow-hidden">
          <div class="absolute top-0 right-0 w-32 h-32 bg-secondary/5 rounded-bl-full pointer-events-none"></div>
          <div class="absolute bottom-0 left-0 w-24 h-24 bg-primary/5 rounded-tr-full pointer-events-none"></div>
          
          {#if activeTask.status === 'completed'}
            <div class="mb-md">
              <span class="material-symbols-outlined text-5xl text-secondary">check_circle</span>
            </div>
            <h4 class="font-headline-md text-headline-md text-on-surface mb-sm">Execution Completed</h4>
            <div class="font-body-reading text-body-reading text-on-surface-variant max-w-sm text-left bg-surface p-md rounded border border-outline-variant max-h-60 overflow-y-auto">
              {activeTask.result || 'Goal successfully executed and verified.'}
            </div>
          {:else if activeTask.status === 'failed'}
            <div class="mb-md">
              <span class="material-symbols-outlined text-5xl text-error">error</span>
            </div>
            <h4 class="font-headline-md text-headline-md text-error mb-sm">Execution Failed</h4>
            <p class="font-body-reading text-body-reading text-on-surface-variant max-w-sm">
              {activeTask.error || 'The task could not be verified successfully.'}
            </p>
          {:else}
            <div class="mb-lg relative">
              <div class="absolute inset-0 bg-secondary/20 rounded-full blur-xl animate-pulse"></div>
              <span class="material-symbols-outlined text-5xl text-outline-variant relative z-10 animate-spin">sync</span>
            </div>
            <h4 class="font-headline-md text-headline-md text-on-surface mb-sm">Execution in progress...</h4>
            <p class="font-body-reading text-body-reading text-on-surface-variant max-w-sm">
              Verified findings will appear here once all steps are completed by the Agent Core.
            </p>
          {/if}
        </div>
      </section>

    </div>
  {/if}
</main>
