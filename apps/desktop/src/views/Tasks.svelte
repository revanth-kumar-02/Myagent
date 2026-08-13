<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Task, TaskStep, ActivityLog } from '$lib/api/types';
  import { navigate } from '$lib/stores/navigation';

  let activeTab: 'overview' | 'activity' | 'result' = 'overview';
  let activeTask: Task | null = null;
  let steps: TaskStep[] = [];
  let activities: ActivityLog[] = [];
  let expandedLogs: Record<string, boolean> = {};

  let isLoading = true;
  let errorMsg = '';
  let unsubscribeWs: (() => void) | null = null;

  onMount(async () => {
    await loadTaskWorkspace();
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
        // Active/running task or latest task
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

    // Append activity item
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

    // Refresh steps on plan/step events
    if (evt.event.includes('step') || evt.event.includes('plan')) {
      if (activeTask) {
        api.getTaskSteps(activeTask.id).then(s => steps = s).catch(() => {});
      }
    }
  }

  function toggleLogExpand(id: string) {
    expandedLogs[id] = !expandedLogs[id];
  }

  function getStatusBadge(status: string) {
    switch (status.toLowerCase()) {
      case 'planning':
        return { label: 'Planning', icon: 'psychology', bg: 'bg-surface-container-high', text: 'text-on-surface-variant' };
      case 'executing':
      case 'running':
        return { label: 'Running', icon: 'sync', bg: 'bg-secondary-container/20 border border-secondary/30', text: 'text-secondary animate-pulse' };
      case 'waiting':
        return { label: 'Waiting for Approval', icon: 'pending', bg: 'bg-tertiary-fixed', text: 'text-on-tertiary-fixed' };
      case 'verifying':
        return { label: 'Verifying', icon: 'fact_check', bg: 'bg-secondary-container/30', text: 'text-on-secondary-container' };
      case 'completed':
      case 'done':
        return { label: 'Completed', icon: 'check_circle', bg: 'bg-surface-container-low border border-outline-variant', text: 'text-secondary' };
      case 'failed':
      case 'error':
        return { label: 'Failed', icon: 'error', bg: 'bg-error-container/30', text: 'text-error' };
      case 'cancelled':
        return { label: 'Cancelled', icon: 'cancel', bg: 'bg-surface-container-high', text: 'text-on-surface-variant' };
      default:
        return { label: status, icon: 'info', bg: 'bg-surface-container', text: 'text-on-surface-variant' };
    }
  }

  function getToolIcon(tool?: string) {
    switch (tool?.toLowerCase()) {
      case 'web_search': return 'search';
      case 'filesystem': return 'folder_open';
      case 'browser': return 'language';
      case 'scheduler': return 'schedule';
      default: return 'build';
    }
  }
</script>

<!-- Task Detail Workspace -->
<main class="ml-64 pt-16 px-margin-desktop pb-margin-desktop min-h-screen bg-background flex flex-col">

  <!-- Back button & Navigation Header -->
  <div class="pt-md pb-xs flex items-center justify-between">
    <button
      on:click={() => navigate('home')}
      class="inline-flex items-center gap-xs font-ui-medium text-[13px] text-on-surface-variant hover:text-primary transition-colors group"
    >
      <span class="material-symbols-outlined text-[18px] group-hover:-translate-x-1 transition-transform">arrow_back</span>
      Back to Home
    </button>
  </div>

  {#if isLoading}
    <div class="flex-1 flex flex-col items-center justify-center py-xxl font-ui-main text-on-surface-variant animate-pulse">
      <span class="material-symbols-outlined text-4xl text-outline-variant mb-md animate-spin">sync</span>
      <p>Loading task workspace...</p>
    </div>
  {:else if errorMsg}
    <div class="my-xl bg-error/10 border border-error/20 text-error rounded-xl p-xl text-center max-w-lg mx-auto">
      <span class="material-symbols-outlined text-3xl mb-xs">warning</span>
      <p class="font-ui-medium text-ui-medium">{errorMsg}</p>
    </div>
  {:else if !activeTask}
    <!-- Empty State -->
    <div class="flex-1 flex flex-col items-center justify-center py-xxl">
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xxl text-center max-w-lg shadow-[0_4px_24px_rgba(106,91,90,0.04)]">
        <span class="material-symbols-outlined text-5xl text-outline-variant mb-md">checklist</span>
        <h3 class="font-headline-md text-headline-md text-primary mb-xs">No Tasks Available</h3>
        <p class="font-body-reading text-body-reading text-on-surface-variant mb-lg">
          No agent execution task is currently active. Submit a goal statement from the Home workspace to trigger autonomous execution.
        </p>
        <button
          on:click={() => navigate('home')}
          class="bg-primary text-on-primary hover:bg-primary-container px-lg py-sm rounded-full font-ui-medium text-ui-medium inline-flex items-center gap-xs shadow-sm transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">add</span>
          New Task Goal
        </button>
      </div>
    </div>
  {:else}
    <!-- TOP HEADER -->
    <header class="py-md border-b border-outline-variant/60 mb-md">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-md mb-xs">
        <div class="flex items-center gap-md flex-wrap">
          <h1 class="font-headline-md text-headline-md text-primary truncate max-w-3xl">
            {activeTask.title}
          </h1>
          <!-- Status Badge -->
          {#await getStatusBadge(activeTask.status) then b}
            <div class="inline-flex items-center gap-xs px-md py-[4px] rounded-full font-label-caps text-label-caps {b.bg} {b.text}">
              <span class="material-symbols-outlined text-[14px]">{b.icon}</span>
              <span>{b.label}</span>
            </div>
          {/await}
        </div>
      </div>

      <!-- Task Description & Meta Context -->
      <p class="font-ui-main text-ui-main text-on-surface-variant max-w-4xl mb-sm">
        {activeTask.description || 'Autonomous goal execution task.'}
      </p>

      <div class="flex items-center gap-lg font-status-log text-status-log text-on-surface-variant/70 flex-wrap">
        <div class="flex items-center gap-xs">
          <span class="material-symbols-outlined text-[16px]">folder_open</span>
          <span>Project: {activeTask.project_id || 'Global Strategy'}</span>
        </div>
        <div class="flex items-center gap-xs">
          <span class="material-symbols-outlined text-[16px]">schedule</span>
          <span>Created: {new Date(activeTask.created_at || Date.now()).toLocaleTimeString()}</span>
        </div>
        <div class="flex items-center gap-xs">
          <span class="material-symbols-outlined text-[16px]">badge</span>
          <span>Task ID: {activeTask.id.slice(0, 8)}...</span>
        </div>
      </div>
    </header>

    <!-- HORIZONTAL TAB SYSTEM -->
    <nav class="flex items-center gap-md border-b border-outline-variant mb-lg">
      <button
        on:click={() => activeTab = 'overview'}
        class="pb-sm font-ui-medium text-ui-medium transition-colors relative flex items-center gap-xs px-xs
          {activeTab === 'overview' ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
      >
        <span class="material-symbols-outlined text-[18px]">account_tree</span>
        Overview
      </button>

      <button
        on:click={() => activeTab = 'activity'}
        class="pb-sm font-ui-medium text-ui-medium transition-colors relative flex items-center gap-xs px-xs
          {activeTab === 'activity' ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
      >
        <span class="material-symbols-outlined text-[18px]">history</span>
        Activity ({activities.length})
      </button>

      <button
        on:click={() => activeTab = 'result'}
        class="pb-sm font-ui-medium text-ui-medium transition-colors relative flex items-center gap-xs px-xs
          {activeTab === 'result' ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
      >
        <span class="material-symbols-outlined text-[18px]">fact_check</span>
        Result
      </button>
    </nav>

    <!-- TAB 1: OVERVIEW -->
    {#if activeTab === 'overview'}
      <div class="space-y-xl max-w-5xl">
        
        <!-- Current Live Activity Banner -->
        <section class="bg-surface-container-lowest border border-outline-variant rounded-xl p-md flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-md">
            <span class="material-symbols-outlined text-secondary text-2xl animate-spin">sync</span>
            <div>
              <div class="font-label-caps text-label-caps text-on-surface-variant">CURRENT ACTIVITY</div>
              <div class="font-ui-medium text-ui-medium text-primary">
                {activities.length > 0 ? activities[0].message : 'Agent initialized and ready...'}
              </div>
            </div>
          </div>
          <span class="font-status-log text-status-log text-on-surface-variant/60">
            {activities.length > 0 ? activities[0].timestamp : ''}
          </span>
        </section>

        <!-- EXECUTION PLAN Timeline -->
        <section>
          <div class="flex items-center justify-between mb-md">
            <h2 class="font-label-caps text-label-caps text-on-surface-variant tracking-wider flex items-center gap-xs">
              <span class="material-symbols-outlined text-[16px]">flag</span>
              EXECUTION PLAN ({steps.length} STEPS)
            </h2>
          </div>

          {#if steps.length === 0}
            <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg text-center font-ui-main text-on-surface-variant/70">
              Generating plan steps...
            </div>
          {:else}
            <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg space-y-md shadow-sm">
              {#each steps as step, i}
                <div class="flex items-start gap-md relative">
                  <!-- Vertical connector line -->
                  {#if i < steps.length - 1}
                    <div class="absolute left-[15px] top-[32px] bottom-[-16px] w-[2px] bg-outline-variant/60"></div>
                  {/if}

                  <!-- Step Status Indicator -->
                  <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 z-10
                    {step.status === 'completed' ? 'bg-secondary/15 text-secondary border border-secondary/30' :
                     step.status === 'executing' ? 'bg-secondary text-on-secondary animate-pulse' :
                     step.status === 'failed' ? 'bg-error/15 text-error border border-error/30' :
                     'bg-surface-container-high text-on-surface-variant border border-outline-variant'}"
                  >
                    {#if step.status === 'completed'}
                      <span class="material-symbols-outlined text-[18px]">check</span>
                    {:else if step.status === 'executing'}
                      <span class="material-symbols-outlined text-[18px] animate-spin">sync</span>
                    {:else if step.status === 'failed'}
                      <span class="material-symbols-outlined text-[18px]">close</span>
                    {:else}
                      <span class="font-status-log text-[12px] font-semibold">{step.step_number}</span>
                    {/if}
                  </div>

                  <!-- Step Details -->
                  <div class="flex-1 pt-xs">
                    <div class="flex items-center justify-between gap-md mb-xs">
                      <h3 class="font-ui-medium text-ui-medium text-primary flex items-center gap-xs">
                        {step.title}
                      </h3>
                      
                      <!-- Tool Pill -->
                      {#if step.tool}
                        <span class="inline-flex items-center gap-xs bg-surface-container border border-outline-variant px-sm py-[2px] rounded font-status-log text-code-sm text-on-surface-variant">
                          <span class="material-symbols-outlined text-[14px]">{getToolIcon(step.tool)}</span>
                          {step.tool}
                        </span>
                      {/if}
                    </div>

                    <p class="font-ui-main text-[14px] text-on-surface-variant">
                      {step.description || 'Step execution objective'}
                    </p>

                    {#if step.result}
                      <div class="mt-sm bg-surface p-sm rounded border border-outline-variant font-status-log text-status-log text-on-surface-variant">
                        Result: {step.result}
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </section>

        <!-- TASK CONTEXT -->
        <section class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg shadow-sm">
          <h2 class="font-label-caps text-label-caps text-on-surface-variant tracking-wider mb-md flex items-center gap-xs">
            <span class="material-symbols-outlined text-[16px]">info</span>
            TASK CONTEXT & PERMISSIONS
          </h2>

          <div class="grid grid-cols-1 md:grid-cols-4 gap-md font-ui-main text-[14px]">
            <div class="p-sm bg-surface rounded border border-outline-variant/60">
              <div class="font-label-caps text-[11px] text-on-surface-variant/70 mb-xs">PROJECT</div>
              <div class="font-ui-medium text-primary">{activeTask.project_id || 'Global Strategy'}</div>
            </div>

            <div class="p-sm bg-surface rounded border border-outline-variant/60">
              <div class="font-label-caps text-[11px] text-on-surface-variant/70 mb-xs">LLM ROUTING</div>
              <div class="font-ui-medium text-primary">Groq / Llama-3.3</div>
            </div>

            <div class="p-sm bg-surface rounded border border-outline-variant/60">
              <div class="font-label-caps text-[11px] text-on-surface-variant/70 mb-xs">TOOL PERMISSIONS</div>
              <div class="font-ui-medium text-primary">Read / Write Sandbox</div>
            </div>

            <div class="p-sm bg-surface rounded border border-outline-variant/60">
              <div class="font-label-caps text-[11px] text-on-surface-variant/70 mb-xs">STATUS</div>
              <div class="font-ui-medium text-secondary uppercase">{activeTask.status}</div>
            </div>
          </div>
        </section>

      </div>
    {/if}

    <!-- TAB 2: ACTIVITY -->
    {#if activeTab === 'activity'}
      <div class="max-w-5xl space-y-md">
        <div class="flex items-center justify-between mb-sm">
          <h2 class="font-label-caps text-label-caps text-on-surface-variant tracking-wider">
            CHRONOLOGICAL EXECUTION LOG
          </h2>
          <span class="font-status-log text-status-log text-on-surface-variant/60">
            {activities.length} Events recorded
          </span>
        </div>

        {#if activities.length === 0}
          <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg text-center font-ui-main text-on-surface-variant/70">
            No activity events recorded yet.
          </div>
        {:else}
          <div class="space-y-sm">
            {#each activities as entry}
              <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-md shadow-sm transition-colors hover:border-outline">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-md">
                    <span class="font-status-log text-status-log text-secondary font-medium">[{entry.timestamp}]</span>
                    <span class="font-ui-medium text-ui-medium text-primary">{entry.message}</span>
                  </div>

                  {#if entry.details}
                    <button
                      on:click={() => toggleLogExpand(entry.id)}
                      class="text-on-surface-variant hover:text-primary font-ui-medium text-[13px] inline-flex items-center gap-xs border border-outline-variant px-sm py-[2px] rounded transition-colors"
                    >
                      {expandedLogs[entry.id] ? 'Hide Details' : 'Technical Details'}
                      <span class="material-symbols-outlined text-[16px]">
                        {expandedLogs[entry.id] ? 'expand_less' : 'expand_more'}
                      </span>
                    </button>
                  {/if}
                </div>

                <!-- Expandable Technical Details -->
                {#if entry.details && expandedLogs[entry.id]}
                  <div class="mt-md pt-md border-t border-outline-variant/60 font-status-log text-code-sm bg-primary text-on-primary p-md rounded overflow-x-auto">
                    <pre>{JSON.stringify(entry.details, null, 2)}</pre>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- TAB 3: RESULT -->
    {#if activeTab === 'result'}
      <div class="max-w-4xl">
        {#if activeTask.status === 'completed'}
          <!-- Completed Verified Result -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xl shadow-sm space-y-lg">
            <div class="flex items-center justify-between border-b border-outline-variant pb-md">
              <div class="flex items-center gap-md">
                <span class="material-symbols-outlined text-3xl text-secondary">check_circle</span>
                <div>
                  <h2 class="font-headline-md text-headline-md text-primary">VERIFIED RESULT</h2>
                  <p class="font-ui-main text-[13px] text-on-surface-variant">Validated by Autonomous Verifier</p>
                </div>
              </div>

              <div class="bg-secondary-container/20 border border-secondary/30 text-secondary px-md py-xs rounded-full font-label-caps text-label-caps">
                VERIFIED & PASSED
              </div>
            </div>

            <!-- Result Summary -->
            <div>
              <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-xs">SUMMARY OF FINDINGS</h3>
              <div class="font-body-reading text-body-reading text-on-surface bg-surface p-lg rounded-lg border border-outline-variant leading-relaxed">
                {activeTask.result || 'Goal successfully completed, synthesized, and verified across all plan steps.'}
              </div>
            </div>

            <!-- Evidence & Verification Meta -->
            <div class="grid grid-cols-2 gap-md pt-sm">
              <div class="p-md bg-surface rounded border border-outline-variant">
                <div class="font-label-caps text-[11px] text-on-surface-variant/70 mb-xs">VERIFICATION STATUS</div>
                <div class="font-ui-medium text-primary flex items-center gap-xs">
                  <span class="material-symbols-outlined text-secondary text-[18px]">verified</span>
                  100% Steps Satisfied
                </div>
              </div>

              <div class="p-md bg-surface rounded border border-outline-variant">
                <div class="font-label-caps text-[11px] text-on-surface-variant/70 mb-xs">GENERATED ARTIFACTS</div>
                <div class="font-ui-medium text-primary">1 Verification Summary</div>
              </div>
            </div>
          </div>
        {:else if activeTask.status === 'failed'}
          <!-- Failed Result -->
          <div class="bg-surface-container-lowest border border-error/30 rounded-xl p-xl shadow-sm space-y-md">
            <div class="flex items-center gap-md text-error">
              <span class="material-symbols-outlined text-3xl">error</span>
              <h2 class="font-headline-md text-headline-md">Execution Failed</h2>
            </div>
            <p class="font-body-reading text-body-reading text-on-surface-variant">
              {activeTask.error || 'The task failed during execution or verification.'}
            </p>
          </div>
        {:else}
          <!-- In Progress State -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xxl text-center shadow-sm">
            <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-secondary-container/20 text-secondary mb-md animate-pulse">
              <span class="material-symbols-outlined text-2xl animate-spin">sync</span>
            </div>
            <h3 class="font-headline-md text-headline-md text-primary mb-xs">Execution in Progress</h3>
            <p class="font-body-reading text-body-reading text-on-surface-variant max-w-md mx-auto">
              The verified result will appear here when the agent completes and validates all plan steps.
            </p>
          </div>
        {/if}
      </div>
    {/if}

  {/if}
</main>
