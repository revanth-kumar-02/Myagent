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
    } final: {
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
        return { label: 'Waiting Approval', icon: 'pending', bg: 'bg-tertiary-fixed', text: 'text-on-tertiary-fixed' };
      case 'verifying':
        return { label: 'Verifying', icon: 'fact_check', bg: 'bg-secondary-container/30', text: 'text-on-secondary-container' };
      case 'completed':
      case 'done':
        return { label: 'Completed', icon: 'check_circle', bg: 'bg-surface-container-low border border-outline-variant/60', text: 'text-secondary' };
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
      case 'list_directory': return 'folder_open';
      case 'search_files': return 'manage_search';
      case 'read_file': return 'description';
      case 'inspect_file': return 'info';
      case 'create_file': return 'note_add';
      case 'edit_file': return 'edit_note';
      case 'move_file': return 'drive_file_move';
      case 'delete_file': return 'delete';
      case 'filesystem': return 'folder_open';
      case 'browser_open':
      case 'browser_navigate':
      case 'browser_back':
      case 'browser_extract':
      case 'browser_click':
      case 'browser_type':
      case 'browser_scroll':
      case 'browser_screenshot':
      case 'browser_download':
      case 'browser_close':
      case 'browser': return 'language';
      case 'scheduler': return 'schedule';
      default: return 'build';
    }
  }

  async function handlePermissionResponse(requestId: string, granted: boolean) {
    try {
      await Promise.allSettled([
        api.respondPermission(requestId, granted),
        api.respondBrowserPermission(requestId, granted)
      ]);
    } catch (err) {
      console.error('Failed to respond to permission request', err);
    }
  }
</script>

<!-- Task Detail Workspace -->
<main class="ml-56 pt-12 px-6 pb-4 h-[calc(100vh-48px)] max-h-[calc(100vh-48px)] bg-background flex flex-col overflow-hidden">

  <!-- Back button -->
  <div class="pt-1 pb-2 flex items-center justify-between">
    <button
      onclick={() => navigate('home')}
      class="inline-flex items-center gap-1 font-ui-medium text-[12px] text-on-surface-variant hover:text-primary transition-colors group"
    >
      <span class="material-symbols-outlined text-[16px] group-hover:-translate-x-0.5 transition-transform">arrow_back</span>
      Back to Home
    </button>
  </div>

  {#if isLoading}
    <div class="flex-1 flex flex-col items-center justify-center py-12 font-ui-main text-[13px] text-on-surface-variant animate-pulse">
      <span class="material-symbols-outlined text-3xl text-outline-variant mb-2 animate-spin">sync</span>
      <p>Loading task workspace...</p>
    </div>
  {:else if errorMsg}
    <div class="my-6 bg-error/10 border border-error/20 text-error rounded-md p-4 text-center max-w-lg mx-auto">
      <span class="material-symbols-outlined text-2xl mb-1">warning</span>
      <p class="font-ui-medium text-[13px]">{errorMsg}</p>
    </div>
  {:else if !activeTask}
    <!-- Empty State -->
    <div class="flex-1 flex flex-col items-center justify-center py-12">
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-8 text-center max-w-md shadow-sm">
        <span class="material-symbols-outlined text-4xl text-outline-variant mb-2">checklist</span>
        <h3 class="font-headline-md text-[18px] text-primary mb-1 font-semibold">No Tasks Available</h3>
        <p class="font-ui-main text-[13px] text-on-surface-variant mb-4">
          No agent execution task is currently active. Submit a goal statement from the Home workspace to trigger autonomous execution.
        </p>
        <button
          onclick={() => navigate('home')}
          class="bg-primary text-on-primary hover:bg-primary-container px-3.5 py-1.5 rounded-full font-ui-medium text-[12px] inline-flex items-center gap-1 shadow-sm transition-colors"
        >
          <span class="material-symbols-outlined text-[16px]">add</span>
          New Task Goal
        </button>
      </div>
    </div>
  {:else}
    <!-- TOP HEADER -->
    <header class="py-2.5 border-b border-outline-variant/50 mb-3">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 mb-1">
        <div class="flex items-center gap-3 flex-wrap">
          <h1 class="font-headline-md text-[18px] text-primary font-semibold truncate max-w-2xl">
            {activeTask.title}
          </h1>
          <!-- Status Badge -->
          <div class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-caps text-[10px] {getStatusBadge(activeTask.status).bg} {getStatusBadge(activeTask.status).text}">
            <span class="material-symbols-outlined text-[12px]">{getStatusBadge(activeTask.status).icon}</span>
            <span>{getStatusBadge(activeTask.status).label}</span>
          </div>
        </div>
      </div>

      <!-- Task Description & Meta Context -->
      <p class="font-ui-main text-[13px] text-on-surface-variant/90 max-w-3xl mb-2">
        {activeTask.description || 'Autonomous goal execution task.'}
      </p>

      <div class="flex items-center gap-4 font-status-log text-[11px] text-on-surface-variant/70 flex-wrap">
        <div class="flex items-center gap-1">
          <span class="material-symbols-outlined text-[14px]">folder_open</span>
          <span>Project: {activeTask.project_id || 'Global Strategy'}</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="material-symbols-outlined text-[14px]">schedule</span>
          <span>Created: {new Date(activeTask.created_at || Date.now()).toLocaleTimeString()}</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="material-symbols-outlined text-[14px]">badge</span>
          <span>Task ID: {activeTask.id.slice(0, 8)}...</span>
        </div>
      </div>
    </header>

    <!-- HORIZONTAL TAB SYSTEM -->
    <nav class="flex items-center gap-4 border-b border-outline-variant/40 mb-4 select-none">
      <button
        onclick={() => activeTab = 'overview'}
        class="pb-1.5 font-ui-medium text-[13px] transition-colors relative flex items-center gap-1.5 px-0.5
          {activeTab === 'overview' ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
      >
        <span class="material-symbols-outlined text-[16px]">account_tree</span>
        Overview
      </button>

      <button
        onclick={() => activeTab = 'activity'}
        class="pb-1.5 font-ui-medium text-[13px] transition-colors relative flex items-center gap-1.5 px-0.5
          {activeTab === 'activity' ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
      >
        <span class="material-symbols-outlined text-[16px]">history</span>
        Activity ({activities.length})
      </button>

      <button
        onclick={() => activeTab = 'result'}
        class="pb-1.5 font-ui-medium text-[13px] transition-colors relative flex items-center gap-1.5 px-0.5
          {activeTab === 'result' ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
      >
        <span class="material-symbols-outlined text-[16px]">fact_check</span>
        Result
      </button>
    </nav>

    <!-- TAB 1: OVERVIEW -->
    {#if activeTab === 'overview'}
      <div class="space-y-4 w-full flex-1 min-h-0 overflow-y-auto pr-1">
        
        <!-- Current Live Activity Banner -->
        <section class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-2.5 flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-2.5">
            <span class="material-symbols-outlined text-secondary text-[20px] animate-spin">sync</span>
            <div>
              <div class="font-label-caps text-[10px] text-on-surface-variant/70 tracking-wider">CURRENT ACTIVITY</div>
              <div class="font-ui-medium text-[13px] text-primary">
                {activities.length > 0 ? activities[0].message : 'Agent initialized and ready...'}
              </div>
            </div>
          </div>
          <span class="font-status-log text-[10px] text-on-surface-variant/60">
            {activities.length > 0 ? activities[0].timestamp : ''}
          </span>
        </section>

        <!-- EXECUTION PLAN Timeline -->
        <section>
          <div class="flex items-center justify-between mb-2">
            <h2 class="font-label-caps text-[11px] text-on-surface-variant/80 tracking-wider flex items-center gap-1 font-semibold">
              <span class="material-symbols-outlined text-[14px]">flag</span>
              EXECUTION PLAN ({steps.length} STEPS)
            </h2>
          </div>

          {#if steps.length === 0}
            <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3 text-center font-ui-main text-[13px] text-on-surface-variant/70">
              Generating plan steps...
            </div>
          {:else}
            <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3.5 space-y-3 shadow-sm">
              {#each steps as step, i}
                <div class="flex items-start gap-3 relative">
                  {#if i < steps.length - 1}
                    <div class="absolute left-[11px] top-[26px] bottom-[-12px] w-[2px] bg-outline-variant/50"></div>
                  {/if}

                  <!-- Step Status Indicator -->
                  <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 z-10 text-[11px]
                    {step.status === 'completed' ? 'bg-secondary/15 text-secondary border border-secondary/30' :
                     step.status === 'executing' ? 'bg-secondary text-on-secondary animate-pulse' :
                     step.status === 'failed' ? 'bg-error/15 text-error border border-error/30' :
                     'bg-surface-container-high text-on-surface-variant border border-outline-variant/60'}"
                  >
                    {#if step.status === 'completed'}
                      <span class="material-symbols-outlined text-[14px]">check</span>
                    {:else if step.status === 'executing'}
                      <span class="material-symbols-outlined text-[14px] animate-spin">sync</span>
                    {:else if step.status === 'failed'}
                      <span class="material-symbols-outlined text-[14px]">close</span>
                    {:else}
                      <span class="font-status-log text-[11px] font-semibold">{step.step_number}</span>
                    {/if}
                  </div>

                  <!-- Step Details -->
                  <div class="flex-1 pt-0.5">
                    <div class="flex items-center justify-between gap-2 mb-0.5">
                      <h3 class="font-ui-medium text-[13px] text-primary flex items-center gap-1 font-medium">
                        {step.title}
                      </h3>
                      
                      <!-- Tool Pill -->
                      {#if step.tool}
                        <span class="inline-flex items-center gap-1 bg-surface-container border border-outline-variant/50 px-1.5 py-0.5 rounded font-status-log text-[10px] text-on-surface-variant">
                          <span class="material-symbols-outlined text-[12px]">{getToolIcon(step.tool)}</span>
                          {step.tool}
                        </span>
                      {/if}
                    </div>

                    <p class="font-ui-main text-[12px] text-on-surface-variant/80">
                      {step.description || 'Step execution objective'}
                    </p>

                    {#if step.result}
                      <div class="mt-1 bg-surface p-2 rounded border border-outline-variant/50 font-status-log text-[11px] text-on-surface-variant truncate">
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
        <section class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3 shadow-sm">
          <h2 class="font-label-caps text-[11px] text-on-surface-variant/80 tracking-wider mb-2 flex items-center gap-1 font-semibold">
            <span class="material-symbols-outlined text-[14px]">info</span>
            TASK CONTEXT & PERMISSIONS
          </h2>

          <div class="grid grid-cols-1 md:grid-cols-4 gap-2 font-ui-main text-[12px]">
            <div class="p-2 bg-surface rounded border border-outline-variant/40">
              <div class="font-label-caps text-[10px] text-on-surface-variant/70 mb-0.5">PROJECT</div>
              <div class="font-ui-medium text-primary text-[12px] truncate">{activeTask.project_id || 'Global Strategy'}</div>
            </div>

            <div class="p-2 bg-surface rounded border border-outline-variant/40">
              <div class="font-label-caps text-[10px] text-on-surface-variant/70 mb-0.5">LLM ROUTING</div>
              <div class="font-ui-medium text-primary text-[12px]">Groq / Llama-3.3</div>
            </div>

            <div class="p-2 bg-surface rounded border border-outline-variant/40">
              <div class="font-label-caps text-[10px] text-on-surface-variant/70 mb-0.5">TOOL PERMISSIONS</div>
              <div class="font-ui-medium text-primary text-[12px]">Read / Write Sandbox</div>
            </div>

            <div class="p-2 bg-surface rounded border border-outline-variant/40">
              <div class="font-label-caps text-[10px] text-on-surface-variant/70 mb-0.5">STATUS</div>
              <div class="font-ui-medium text-secondary uppercase text-[12px]">{activeTask.status}</div>
            </div>
          </div>
        </section>

      </div>
    {/if}

    <!-- TAB 2: ACTIVITY -->
    {#if activeTab === 'activity'}
      <div class="w-full flex-1 min-h-0 overflow-y-auto space-y-2.5 pr-1">

        <div class="flex items-center justify-between mb-1">
          <h2 class="font-label-caps text-[11px] text-on-surface-variant/80 tracking-wider font-semibold">
            CHRONOLOGICAL EXECUTION LOG
          </h2>
          <span class="font-status-log text-[10px] text-on-surface-variant/60">
            {activities.length} Events recorded
          </span>
        </div>

        {#if activities.length === 0}
          <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3 text-center font-ui-main text-[13px] text-on-surface-variant/70">
            No activity events recorded yet.
          </div>
        {:else}
          <div class="space-y-1.5">
            {#each activities as entry}
              <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-2.5 shadow-sm transition-colors hover:border-outline/50">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <span class="font-status-log text-[11px] text-secondary font-medium">[{entry.timestamp}]</span>
                    <span class="font-ui-medium text-[12px] text-primary">{entry.message}</span>
                  </div>

                  {#if entry.details}
                    <button
                      onclick={() => toggleLogExpand(entry.id)}
                      class="text-on-surface-variant hover:text-primary font-ui-medium text-[11px] inline-flex items-center gap-1 border border-outline-variant/50 px-1.5 py-0.5 rounded transition-colors"
                    >
                      {expandedLogs[entry.id] ? 'Hide Details' : 'Technical Details'}
                      <span class="material-symbols-outlined text-[14px]">
                        {expandedLogs[entry.id] ? 'expand_less' : 'expand_more'}
                      </span>
                    </button>
                  {/if}
                </div>

                {#if entry.details && expandedLogs[entry.id]}
                  <div class="mt-2 pt-2 border-t border-outline-variant/40 font-status-log text-[11px] bg-primary text-on-primary p-2 rounded overflow-x-auto">
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
      <div class="w-full flex-1 min-h-0 overflow-y-auto pr-1">
        {#if activeTask.status === 'completed'}
          <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 shadow-sm space-y-3">
            <div class="flex items-center justify-between border-b border-outline-variant/40 pb-2.5">
              <div class="flex items-center gap-2.5">
                <span class="material-symbols-outlined text-2xl text-secondary">check_circle</span>
                <div>
                  <h2 class="font-headline-md text-[16px] text-primary font-semibold">VERIFIED RESULT</h2>
                  <p class="font-ui-main text-[12px] text-on-surface-variant">Validated by Autonomous Verifier</p>
                </div>
              </div>

              <div class="bg-secondary-container/20 border border-secondary/30 text-secondary px-2.5 py-0.5 rounded-full font-label-caps text-[10px]">
                VERIFIED & PASSED
              </div>
            </div>

            <div>
              <h3 class="font-label-caps text-[11px] text-on-surface-variant/80 mb-1 tracking-wider">SUMMARY OF FINDINGS</h3>
              <div class="font-ui-main text-[13px] text-on-surface bg-surface p-3 rounded-md border border-outline-variant/50 leading-normal">
                {activeTask.result || 'Goal successfully completed, synthesized, and verified across all plan steps.'}
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2.5 pt-1">
              <div class="p-2.5 bg-surface rounded-md border border-outline-variant/40">
                <div class="font-label-caps text-[10px] text-on-surface-variant/70 mb-0.5">VERIFICATION STATUS</div>
                <div class="font-ui-medium text-[12px] text-primary flex items-center gap-1">
                  <span class="material-symbols-outlined text-secondary text-[16px]">verified</span>
                  100% Steps Satisfied
                </div>
              </div>

              <div class="p-2.5 bg-surface rounded-md border border-outline-variant/40">
                <div class="font-label-caps text-[10px] text-on-surface-variant/70 mb-0.5">GENERATED ARTIFACTS</div>
                <div class="font-ui-medium text-[12px] text-primary">1 Verification Summary</div>
              </div>
            </div>
          </div>
        {:else if activeTask.status === 'failed'}
          <div class="bg-surface-container-lowest border border-error/30 rounded-md p-4 shadow-sm space-y-2">
            <div class="flex items-center gap-2 text-error">
              <span class="material-symbols-outlined text-2xl">error</span>
              <h2 class="font-headline-md text-[16px] font-semibold">Execution Failed</h2>
            </div>
            <p class="font-ui-main text-[13px] text-on-surface-variant">
              {activeTask.error || 'The task failed during execution or verification.'}
            </p>
          </div>
        {:else}
          <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-8 text-center shadow-sm">
            <div class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-secondary-container/20 text-secondary mb-2 animate-pulse">
              <span class="material-symbols-outlined text-xl animate-spin">sync</span>
            </div>
            <h3 class="font-headline-md text-[16px] text-primary mb-1 font-semibold">Execution in Progress</h3>
            <p class="font-ui-main text-[13px] text-on-surface-variant max-w-md mx-auto">
              The verified result will appear here when the agent completes and validates all plan steps.
            </p>
          </div>
        {/if}
      </div>
    {/if}

  {/if}
</main>
