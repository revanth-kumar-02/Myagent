<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Automation, AutomationRun } from '$lib/api/types';

  let automations: Automation[] = [];
  let selectedAutomation: Automation | null = null;
  let runs: AutomationRun[] = [];
  let isLoading = true;
  let errorMsg = '';

  // NL Creation state
  let nlPrompt = '';
  let isParsingNL = false;
  let parsedPreview: any = null;
  let showNLModal = false;

  onMount(async () => {
    await loadAutomations();
  });

  async function loadAutomations() {
    isLoading = true;
    errorMsg = '';
    try {
      automations = await api.getAutomations();
    } catch (err: any) {
      errorMsg = err.message || 'Failed to load automations';
    } finally {
      isLoading = false;
    }
  }

  async function handleToggle(auto: Automation) {
    try {
      if (auto.is_active) {
        await api.disableAutomation(auto.id);
      } else {
        await api.enableAutomation(auto.id);
      }
      await loadAutomations();
    } catch (err: any) {
      alert(`Error toggling automation: ${err.message}`);
    }
  }

  async function handleRunNow(auto: Automation) {
    try {
      await api.runAutomation(auto.id);
      alert(`Automation '${auto.title}' triggered in background.`);
      await loadAutomations();
    } catch (err: any) {
      alert(`Error running automation: ${err.message}`);
    }
  }

  async function handleViewHistory(auto: Automation) {
    selectedAutomation = auto;
    try {
      runs = await api.getAutomationRuns(auto.id);
    } catch (err: any) {
      runs = [];
    }
  }

  async function handleParseNL() {
    if (!nlPrompt.trim()) return;
    isParsingNL = true;
    try {
      const res = await api.parseNLAutomation(nlPrompt);
      parsedPreview = res.definition;
      showNLModal = true;
    } catch (err: any) {
      alert(`Parsing failed: ${err.message}`);
    } finally {
      isParsingNL = false;
    }
  }

  async function confirmCreateNL() {
    if (!parsedPreview) return;
    try {
      await api.createAutomation({
        title: parsedPreview.title,
        description: parsedPreview.description,
        trigger_type: parsedPreview.trigger_type,
        trigger_config: parsedPreview.trigger_config,
        workflow_config: {
          notification_level: parsedPreview.notification_level,
          condition: parsedPreview.condition,
          allowed_tools: parsedPreview.allowed_tools,
          max_retries: parsedPreview.max_retries
        },
        is_active: true
      });
      showNLModal = false;
      nlPrompt = '';
      parsedPreview = null;
      await loadAutomations();
    } catch (err: any) {
      alert(`Failed to save automation: ${err.message}`);
    }
  }
</script>

<main class="ml-56 pt-12 px-6 pb-6 min-h-[calc(100vh-48px)] bg-background flex flex-col flex-1 animate-page-enter">
  <div class="w-full max-w-6xl flex-1 flex flex-col min-h-0 pt-2 pb-4">

    <!-- Header -->
    <header class="mb-4 flex justify-between items-end border-b border-outline-variant/40 pb-3 shrink-0">
      <div>
        <h2 class="font-headline-md text-[18px] text-primary font-semibold mb-0.5">Automations</h2>
        <p class="font-ui-main text-[13px] text-on-surface-variant">
          Persistent agentic workflows, triggers, and conditional execution.
        </p>
      </div>
      <button 
        on:click={() => (showNLModal = true)}
        class="btn-primary"
      >
        <span class="material-symbols-outlined text-[16px]">add</span>
        New Workflow
      </button>
    </header>

    <!-- Natural Language Prompt Creator Bar -->
    <div class="mb-4 bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3 shadow-sm flex items-center gap-2">
      <span class="material-symbols-outlined text-primary text-[20px]">auto_awesome</span>
      <input
        type="text"
        bind:value={nlPrompt}
        placeholder="e.g., 'Every weekday at 9 AM, check my projects and notify me if tests fail.'"
        class="flex-1 bg-background border border-outline-variant/40 rounded px-3 py-1.5 text-[13px] text-primary focus:outline-none focus:border-primary"
        on:keydown={(e) => e.key === 'Enter' && handleParseNL()}
      />
      <button
        on:click={handleParseNL}
        disabled={isParsingNL || !nlPrompt.trim()}
        class="btn-secondary disabled:opacity-50"
      >
        {#if isParsingNL}
          <span class="material-symbols-outlined text-[16px] animate-spin">refresh</span>
        {:else}
          <span class="material-symbols-outlined text-[16px]">bolt</span>
        {/if}
        Parse NL
      </button>
    </div>

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
      <div class="flex-1 flex gap-4 overflow-hidden">
        <!-- Automation Cards List -->
        <div class="flex-1 overflow-y-auto space-y-3 pr-1">
          {#each automations as auto}
            <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 shadow-sm hover:border-primary/40 transition-colors">
              <div class="flex justify-between items-start mb-2">
                <div>
                  <h3 class="font-ui-medium text-[15px] text-primary font-medium">{auto.title}</h3>
                  <p class="font-ui-main text-[13px] text-on-surface-variant mt-0.5">{auto.description || 'No description'}</p>
                </div>
                <div class="flex items-center gap-2">
                  <span class={`px-2 py-0.5 rounded-full font-label-caps text-[10px] flex items-center gap-1 ${
                    auto.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-surface-variant text-on-surface-variant'
                  }`}>
                    <span class="material-symbols-outlined text-[12px]">{auto.is_active ? 'play_arrow' : 'pause'}</span>
                    {auto.is_active ? 'Active' : 'Paused'}
                  </span>
                </div>
              </div>

              <div class="flex items-center justify-between text-[11px] font-mono text-on-surface-variant mt-3 pt-2 border-t border-outline-variant/40">
                <div class="flex items-center gap-3">
                  <span>Trigger: <strong class="text-primary">{auto.trigger_type}</strong></span>
                  {#if auto.last_run_at}
                    <span>Last Run: <strong class="text-primary">{new Date(auto.last_run_at).toLocaleTimeString()}</strong></span>
                  {/if}
                  {#if auto.last_run_status}
                    <span class={`font-semibold ${auto.last_run_status === 'COMPLETED' ? 'text-emerald-600' : 'text-amber-600'}`}>
                      [{auto.last_run_status}]
                    </span>
                  {/if}
                </div>

                <div class="flex items-center gap-2">
                  <button
                    on:click={() => handleRunNow(auto)}
                    class="btn-secondary btn-sm"
                  >
                    <span class="material-symbols-outlined text-[14px]">play_arrow</span> Run Now
                  </button>
                  <button
                    on:click={() => handleToggle(auto)}
                    class="btn-secondary btn-sm"
                  >
                    {auto.is_active ? 'Pause' : 'Enable'}
                  </button>
                  <button
                    on:click={() => handleViewHistory(auto)}
                    class="btn-secondary btn-sm"
                  >
                    <span class="material-symbols-outlined text-[14px]">history</span> Runs
                  </button>
                </div>
              </div>
            </div>
          {/each}
        </div>

        <!-- History Drawer -->
        {#if selectedAutomation}
          <div class="w-80 bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 flex flex-col overflow-hidden">
            <div class="flex items-center justify-between border-b border-outline-variant/40 pb-2 mb-3">
              <h4 class="font-ui-medium text-[14px] text-primary font-semibold">Run History</h4>
              <button on:click={() => (selectedAutomation = null)} class="btn-ghost btn-sm">
                <span class="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
            <p class="text-[11px] font-mono text-on-surface-variant mb-2 truncate">{selectedAutomation.title}</p>
            
            <div class="flex-1 overflow-y-auto space-y-2 pr-1">
              {#if runs.length === 0}
                <div class="text-[12px] text-on-surface-variant text-center py-6">No runs recorded yet.</div>
              {:else}
                {#each runs as r}
                  <div class="bg-background border border-outline-variant/40 rounded p-2.5 text-[11px]">
                    <div class="flex justify-between font-mono font-semibold mb-1">
                      <span class={r.status === 'COMPLETED' ? 'text-emerald-600' : 'text-rose-600'}>{r.status}</span>
                      <span class="text-on-surface-variant">{new Date(r.started_at).toLocaleTimeString()}</span>
                    </div>
                    {#if r.result_summary}
                      <p class="text-on-surface-variant text-[11px] truncate mb-1">{r.result_summary}</p>
                    {/if}
                    <div class="text-[10px] text-on-surface-variant/80 font-mono flex justify-between pt-1 border-t border-outline-variant/20">
                      <span>Duration: {r.duration_seconds || 0}s</span>
                      <span>Tools: {r.tool_call_count}</span>
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Natural Language Modal -->
    {#if showNLModal}
      <div class="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg w-full max-w-lg p-5 shadow-xl">
          <h3 class="font-headline-md text-[16px] text-primary font-semibold mb-2">Create Automation</h3>
          
          {#if parsedPreview}
            <div class="bg-background border border-outline-variant/40 rounded p-3 text-[12px] space-y-2 font-mono mb-4">
              <div><strong class="text-primary">Title:</strong> {parsedPreview.title}</div>
              <div><strong class="text-primary">Trigger:</strong> {parsedPreview.trigger_type} ({JSON.stringify(parsedPreview.trigger_config)})</div>
              <div><strong class="text-primary">Notification:</strong> {parsedPreview.notification_level}</div>
              <div><strong class="text-primary">Goal:</strong> {parsedPreview.description}</div>
            </div>
            <div class="flex justify-end gap-2">
              <button on:click={() => (showNLModal = false)} class="btn-secondary">Cancel</button>
              <button on:click={confirmCreateNL} class="btn-primary">Confirm & Activate</button>
            </div>
          {:else}
            <textarea
              bind:value={nlPrompt}
              rows="4"
              placeholder="Enter automation prompt..."
              class="w-full bg-background border border-outline-variant/40 rounded p-2 text-[12px] mb-3 focus:outline-none"
            ></textarea>
            <div class="flex justify-end gap-2">
              <button on:click={() => (showNLModal = false)} class="btn-secondary">Cancel</button>
              <button on:click={handleParseNL} class="btn-primary">Parse</button>
            </div>
          {/if}
        </div>
      </div>
    {/if}

  </div>
</main>
