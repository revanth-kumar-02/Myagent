<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Project, Workspace } from '$lib/api/types';

  let workspace: Workspace | null = null;
  let projects: Project[] = [];
  let selectedProject: Project | null = null;
  let activeDetailTab: 'overview' | 'files' | 'research' | 'tasks' | 'context' | 'automations' = 'overview';

  let searchQuery = '';
  let sortBy: 'recent' | 'alphabetical' = 'recent';

  let isLoading = true;
  let isScanning = false;
  let errorMsg = '';
  
  let showChangeWorkspaceModal = false;
  let newWorkspacePath = '';
  let modalErrorMsg = '';
  let modalIsScanning = false;

  onMount(async () => {
    await loadWorkspaceAndProjects();
  });

  async function loadWorkspaceAndProjects() {
    isLoading = true;
    errorMsg = '';
    try {
      workspace = await api.getWorkspace();
      if (workspace) {
        newWorkspacePath = workspace.path;
      }
      projects = await api.getProjects();
    } catch (err: any) {
      errorMsg = err.message || 'Could not connect to Cocoa Agent.';
    } finally {
      isLoading = false;
    }
  }

  async function handleRescan() {
    isScanning = true;
    errorMsg = '';
    try {
      const res = await api.scanWorkspace();
      workspace = res.workspace;
      projects = res.projects;
    } catch (err: any) {
      errorMsg = err.message || 'Could not connect to Cocoa Agent.';
    } finally {
      isScanning = false;
    }
  }

  async function handleSetWorkspace() {
    modalErrorMsg = '';
    const cleanPath = newWorkspacePath.trim();
    if (!cleanPath) {
      modalErrorMsg = 'Please enter a valid workspace directory path.';
      return;
    }

    modalIsScanning = true;
    try {
      const res = await api.setWorkspace(cleanPath);
      workspace = res.workspace;
      projects = res.projects;
      showChangeWorkspaceModal = false;
    } catch (err: any) {
      modalErrorMsg = err.message || 'Could not connect to Cocoa Agent.';
    } finally {
      modalIsScanning = false;
    }
  }

  function openChangeModal() {
    modalErrorMsg = '';
    newWorkspacePath = workspace?.path || '';
    showChangeWorkspaceModal = true;
  }

  function selectProject(proj: Project) {
    selectedProject = proj;
    activeDetailTab = 'overview';
  }

  function backToProjectList() {
    selectedProject = null;
  }

  $: filteredProjects = projects
    .filter(p => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        p.title.toLowerCase().includes(q) ||
        (p.languages && p.languages.some(l => l.toLowerCase().includes(q))) ||
        (p.frameworks && p.frameworks.some(f => f.toLowerCase().includes(q))) ||
        (p.path && p.path.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => {
      if (sortBy === 'alphabetical') {
        return a.title.localeCompare(b.title);
      }
      const tA = new Date(a.last_modified || a.created_at || 0).getTime();
      const tB = new Date(b.last_modified || b.created_at || 0).getTime();
      return tB - tA;
    });

  function formatTimeAgo(dateStr?: string) {
    if (!dateStr) return 'Recently';
    const date = new Date(dateStr);
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSeconds < 60) return 'Just now';
    if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
    if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
    if (diffSeconds < 172800) return 'Yesterday';
    return `${Math.floor(diffSeconds / 86400)}d ago`;
  }
</script>

<main class="ml-64 pt-16 px-margin-desktop pb-margin-desktop min-h-screen bg-background flex flex-col">

  {#if selectedProject}
    <!-- PROJECT DETAIL VIEW -->
    <div class="space-y-md">
      <!-- Back Navigation Header -->
      <div class="pt-md pb-xs">
        <button
          on:click={backToProjectList}
          class="inline-flex items-center gap-xs font-ui-medium text-[13px] text-on-surface-variant hover:text-primary transition-colors group"
        >
          <span class="material-symbols-outlined text-[18px] group-hover:-translate-x-1 transition-transform">arrow_back</span>
          Back to Projects Browser
        </button>
      </div>

      <!-- Detail Header -->
      <header class="py-md border-b border-outline-variant/60">
        <div class="flex items-center justify-between gap-md mb-xs">
          <div class="flex items-center gap-md">
            <span class="material-symbols-outlined text-primary text-3xl">folder_open</span>
            <div>
              <h1 class="font-headline-md text-headline-md text-primary">{selectedProject.title}</h1>
              <p class="font-status-log text-code-sm text-on-surface-variant/80">{selectedProject.path}</p>
            </div>
          </div>

          <div class="flex items-center gap-xs">
            {#if selectedProject.git_repository}
              <span class="inline-flex items-center gap-xs bg-secondary-container/20 border border-secondary/30 text-secondary px-md py-[4px] rounded-full font-label-caps text-label-caps">
                <span class="material-symbols-outlined text-[14px]">code_blocks</span>
                Git Repository
              </span>
            {/if}
          </div>
        </div>

        <!-- Language & Framework Pills -->
        <div class="flex items-center gap-xs flex-wrap mt-md">
          {#if (!selectedProject.languages || selectedProject.languages.length === 0) && (!selectedProject.frameworks || selectedProject.frameworks.length === 0)}
            <span class="bg-surface text-on-surface-variant/70 border border-outline-variant px-sm py-[2px] rounded font-label-caps text-label-caps italic">
              Stack not detected
            </span>
          {:else}
            {#if selectedProject.languages}
              {#each selectedProject.languages as lang}
                <span class="bg-primary/10 border border-primary/20 text-primary px-sm py-[2px] rounded font-label-caps text-label-caps">
                  {lang}
                </span>
              {/each}
            {/if}
            {#if selectedProject.frameworks}
              {#each selectedProject.frameworks as fw}
                <span class="bg-surface-container-high border border-outline-variant text-on-surface-variant px-sm py-[2px] rounded font-label-caps text-label-caps">
                  {fw}
                </span>
              {/each}
            {/if}
          {/if}
        </div>
      </header>

      <!-- Detail Tabs -->
      <nav class="flex items-center gap-md border-b border-outline-variant mb-lg">
        {#each ['overview', 'files', 'research', 'tasks', 'context', 'automations'] as tab}
          <button
            on:click={() => activeDetailTab = tab as any}
            class="pb-sm font-ui-medium text-ui-medium capitalize transition-colors relative flex items-center gap-xs px-xs
              {activeDetailTab === tab ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
          >
            {tab}
          </button>
        {/each}
      </nav>

      <!-- Tab Content Area -->
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xl shadow-sm min-h-[300px]">
        {#if activeDetailTab === 'overview'}
          <div class="space-y-md">
            <h3 class="font-label-caps text-label-caps text-on-surface-variant">WORKSPACE CONTEXT</h3>
            <p class="font-body-reading text-body-reading text-on-surface">
              {selectedProject.description || `Local repository configured at ${selectedProject.path}. This workspace context is active for Cocoa agent operations.`}
            </p>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-md pt-md">
              <div class="p-sm bg-surface rounded border border-outline-variant">
                <div class="font-label-caps text-[11px] text-on-surface-variant mb-xs">LAST MODIFIED</div>
                <div class="font-ui-medium text-primary">{formatTimeAgo(selectedProject.last_modified)}</div>
              </div>
              <div class="p-sm bg-surface rounded border border-outline-variant">
                <div class="font-label-caps text-[11px] text-on-surface-variant mb-xs">LAST SCANNED</div>
                <div class="font-ui-medium text-primary">{formatTimeAgo(selectedProject.last_scanned)}</div>
              </div>
            </div>
          </div>
        {:else}
          <div class="text-center py-xl text-on-surface-variant font-ui-main">
            <span class="material-symbols-outlined text-4xl text-outline-variant mb-xs">folder_open</span>
            <p class="capitalize">{activeDetailTab} workspace view active for {selectedProject.title}.</p>
          </div>
        {/if}
      </div>
    </div>
  {:else}

    <!-- PROJECTS LIST / REPOSITORY BROWSER -->
    <header class="py-md border-b border-outline-variant/60 mb-lg">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-md mb-sm">
        <div>
          <h2 class="font-label-caps text-label-caps text-on-surface-variant mb-xs">LOCAL WORKSPACE BROWSER</h2>
          <h1 class="font-headline-md text-headline-md text-primary">Projects</h1>
        </div>

        <div class="flex items-center gap-sm">
          <button
            on:click={handleRescan}
            disabled={isScanning}
            class="bg-surface border border-outline-variant hover:border-outline text-primary px-md py-sm rounded-lg font-ui-medium text-ui-medium inline-flex items-center gap-xs transition-colors shadow-sm disabled:opacity-50"
          >
            <span class="material-symbols-outlined text-[18px] {isScanning ? 'animate-spin' : ''}">sync</span>
            {isScanning ? 'Scanning workspace...' : 'Rescan Workspace'}
          </button>

          <button
            on:click={openChangeModal}
            class="bg-primary text-on-primary hover:bg-primary-container text-on-primary px-md py-sm rounded-lg font-ui-medium text-ui-medium inline-flex items-center gap-xs transition-colors shadow-sm"
          >
            <span class="material-symbols-outlined text-[18px]">folder</span>
            Change Folder
          </button>
        </div>
      </div>

      <!-- Current Workspace Banner -->
      <div class="flex items-center justify-between bg-surface-container-low border border-outline-variant rounded-lg px-md py-sm font-status-log text-code-sm text-on-surface-variant">
        <div class="flex items-center gap-xs truncate">
          <span class="material-symbols-outlined text-[16px] text-secondary">folder_managed</span>
          <span class="font-medium text-primary">Your workspace:</span>
          <span class="truncate">{workspace?.path || '~/Projects'}</span>
        </div>
        <span class="text-[12px] opacity-75">{filteredProjects.length} Projects Discovered</span>
      </div>
    </header>

    <!-- Search & Filter Control Bar -->
    <div class="flex flex-col sm:flex-row items-center justify-between gap-md mb-lg">
      <!-- Search Input -->
      <div class="relative w-full sm:w-96">
        <span class="material-symbols-outlined absolute left-md top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">search</span>
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search projects by name, language, or path..."
          class="w-full bg-surface-container-lowest border border-outline-variant rounded-lg pl-xl pr-md py-sm font-ui-main text-ui-main text-primary placeholder:text-on-surface-variant/60 focus:border-secondary focus:outline-none transition-colors"
        />
      </div>

      <!-- Sort Controls -->
      <div class="flex items-center gap-xs self-end sm:self-auto font-ui-medium text-[13px] text-on-surface-variant">
        <span>Sort:</span>
        <select
          bind:value={sortBy}
          class="bg-surface-container-lowest border border-outline-variant rounded-lg px-sm py-xs text-primary font-ui-medium focus:outline-none"
        >
          <option value="recent">Recently Modified</option>
          <option value="alphabetical">Alphabetical</option>
        </select>
      </div>
    </div>

    <!-- UI STATES -->
    {#if isLoading || isScanning}
      <div class="flex-1 flex flex-col items-center justify-center py-xxl text-on-surface-variant animate-pulse">
        <span class="material-symbols-outlined text-4xl mb-md animate-spin">sync</span>
        <p class="font-ui-main">Scanning workspace...</p>
      </div>
    {:else if errorMsg}
      <div class="bg-error/10 border border-error/20 text-error rounded-xl p-lg font-ui-main my-md text-center">
        <span class="material-symbols-outlined text-2xl mb-xs">warning</span>
        <p>{errorMsg}</p>
      </div>
    {:else if filteredProjects.length === 0}
      <!-- Empty State -->
      <div class="flex-1 flex flex-col items-center justify-center py-xxl">
        <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xxl text-center max-w-lg shadow-sm">
          <span class="material-symbols-outlined text-5xl text-outline-variant mb-md">manage_search</span>
          <h3 class="font-headline-md text-headline-md text-primary mb-xs">No projects found</h3>
          <p class="font-body-reading text-body-reading text-on-surface-variant mb-lg">
            No project markers (`package.json`, `pyproject.toml`, `Cargo.toml`, `.git`, etc.) were discovered inside <span class="font-status-log text-code-sm">{workspace?.path || '~/Projects'}</span>.
          </p>
          <button
            on:click={openChangeModal}
            class="bg-primary text-on-primary hover:bg-primary-container px-lg py-sm rounded-full font-ui-medium text-ui-medium inline-flex items-center gap-xs shadow-sm transition-colors"
          >
            <span class="material-symbols-outlined text-[18px]">folder</span>
            Select Another Workspace Directory
          </button>
        </div>
      </div>
    {:else}
      <!-- PROJECT CARDS GRID -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-lg">
        {#each filteredProjects as proj}
          <div
            on:click={() => selectProject(proj)}
            on:keydown={(e) => e.key === 'Enter' && selectProject(proj)}
            role="button"
            tabindex="0"
            class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg hover:border-secondary hover:shadow-md transition-all cursor-pointer flex flex-col justify-between group"
          >
            <div>
              <!-- Top Row: Name & Git Badge -->
              <div class="flex items-start justify-between gap-md mb-xs">
                <h3 class="font-ui-medium text-ui-medium text-primary group-hover:text-secondary transition-colors flex items-center gap-xs">
                  <span class="material-symbols-outlined text-primary group-hover:text-secondary text-[20px]">folder_open</span>
                  {proj.title}
                </h3>

                {#if proj.git_repository}
                  <span class="inline-flex items-center gap-[4px] bg-secondary-container/20 text-secondary border border-secondary/30 px-xs py-[2px] rounded font-label-caps text-[11px] shrink-0">
                    <span class="material-symbols-outlined text-[12px]">code_blocks</span>
                    Git Repository
                  </span>
                {/if}
              </div>

              <!-- Subtitle Path -->
              <p class="font-status-log text-[12px] text-on-surface-variant/70 mb-md truncate">
                {proj.path}
              </p>

              <!-- Language & Framework Tags -->
              <div class="flex items-center gap-xs flex-wrap mb-md">
                {#if (!proj.languages || proj.languages.length === 0) && (!proj.frameworks || proj.frameworks.length === 0)}
                  <span class="bg-surface text-on-surface-variant/70 border border-outline-variant/60 px-sm py-[2px] rounded font-label-caps text-[11px] italic">
                    Stack not detected
                  </span>
                {:else}
                  {#if proj.languages}
                    {#each proj.languages as lang}
                      <span class="bg-surface-container-high text-primary border border-outline-variant px-sm py-[2px] rounded font-label-caps text-[11px]">
                        {lang}
                      </span>
                    {/each}
                  {/if}

                  {#if proj.frameworks}
                    {#each proj.frameworks as fw}
                      <span class="bg-surface text-on-surface-variant border border-outline-variant/60 px-sm py-[2px] rounded font-label-caps text-[11px]">
                        {fw}
                      </span>
                    {/each}
                  {/if}
                {/if}
              </div>
            </div>

            <!-- Footer: Last Modified -->
            <div class="pt-sm border-t border-outline-variant/50 flex items-center justify-between text-on-surface-variant/70 font-status-log text-[12px]">
              <span>Updated {formatTimeAgo(proj.last_modified)}</span>
              <span class="material-symbols-outlined text-[16px] group-hover:translate-x-1 transition-transform">chevron_right</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}

  {/if}

  <!-- CHANGE WORKSPACE MODAL -->
  {#if showChangeWorkspaceModal}
    <div class="fixed inset-0 bg-primary/40 backdrop-blur-xs flex items-center justify-center z-50 p-md">
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-xl max-w-lg w-full shadow-2xl space-y-md">
        <div class="flex items-center justify-between border-b border-outline-variant pb-sm">
          <h3 class="font-headline-md text-[20px] text-primary">Select Workspace Directory</h3>
          <button
            on:click={() => showChangeWorkspaceModal = false}
            disabled={modalIsScanning}
            class="text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <p class="font-ui-main text-[14px] text-on-surface-variant">
          Enter the absolute path to your root project directory (e.g. <span class="font-status-log text-code-sm">/home/rev/My Personal Space/Projects</span>). Cocoa will automatically discover all project repositories inside.
        </p>

        {#if modalErrorMsg}
          <div class="bg-error/10 border border-error/20 text-error rounded-lg p-sm font-ui-main text-[13px] flex items-center gap-xs">
            <span class="material-symbols-outlined text-[18px]">error</span>
            <span>{modalErrorMsg}</span>
          </div>
        {/if}

        <div>
          <label for="workspace-path-input" class="font-ui-medium text-ui-medium text-primary block mb-xs">Workspace Directory Path</label>
          <input
            id="workspace-path-input"
            type="text"
            bind:value={newWorkspacePath}
            disabled={modalIsScanning}
            placeholder="/home/user/Projects"
            class="w-full bg-surface border border-outline-variant rounded-lg px-md py-sm font-status-log text-code-sm text-primary focus:border-secondary focus:outline-none transition-colors disabled:opacity-50"
          />
        </div>

        <div class="flex items-center justify-end gap-sm pt-sm">
          <button
            on:click={() => showChangeWorkspaceModal = false}
            disabled={modalIsScanning}
            class="px-md py-sm border border-outline-variant rounded-lg font-ui-medium text-ui-medium text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            on:click={handleSetWorkspace}
            disabled={modalIsScanning}
            class="bg-primary text-on-primary hover:bg-primary-container px-lg py-sm rounded-lg font-ui-medium text-ui-medium transition-colors inline-flex items-center gap-xs disabled:opacity-50"
          >
            {#if modalIsScanning}
              <span class="material-symbols-outlined text-[18px] animate-spin">sync</span>
              Scanning workspace...
            {:else}
              Scan & Save
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}

</main>
