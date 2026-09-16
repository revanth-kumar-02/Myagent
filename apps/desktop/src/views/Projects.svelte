<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { Project, Workspace, RagStatus, RagChunkResult } from '$lib/api/types';

  let workspace: Workspace | null = null;
  let projects: Project[] = [];
  let selectedProject: Project | null = null;
  let projectMemories: any[] = [];
  let activeDetailTab: 'overview' | 'files' | 'research' | 'tasks' | 'context' | 'automations' = 'overview';

  // RAG state
  let ragStatus: RagStatus | null = null;
  let ragSearchQuery = '';
  let ragSearchResults: RagChunkResult[] = [];
  let isRagIndexing = false;
  let isRagSearching = false;
  let ragMsg = '';

  let searchQuery = '';
  let sortBy: 'recent' | 'alphabetical' = 'recent';

  let isLoading = true;
  let isScanning = false;
  let errorMsg = '';
  
  let showChangeWorkspaceModal = false;
  let newWorkspacePath = '';
  let modalErrorMsg = '';
  let modalIsScanning = false;

  let memorySearchQuery = '';
  let isKnowledgeRescanning = false;

  async function handleSearchMemories() {
    if (!selectedProject) return;
    if (!memorySearchQuery.trim()) {
      projectMemories = await api.getMemories(selectedProject.id);
      return;
    }
    try {
      projectMemories = await api.searchMemories(memorySearchQuery, selectedProject.id);
    } catch (e) {}
  }

  async function handleVerifyMemory(memId: string) {
    try {
      await api.verifyMemory(memId);
      if (selectedProject) projectMemories = await api.getMemories(selectedProject.id);
    } catch (e) {}
  }

  async function handleArchiveMemory(memId: string) {
    try {
      await api.archiveMemory(memId);
      if (selectedProject) projectMemories = await api.getMemories(selectedProject.id);
    } catch (e) {}
  }

  async function handleRescanKnowledge() {
    if (!selectedProject) return;
    isKnowledgeRescanning = true;
    try {
      await api.refreshProjectKnowledge(selectedProject.id);
      projectMemories = await api.getMemories(selectedProject.id);
    } catch (e) {}
    finally {
      isKnowledgeRescanning = false;
    }
  }

  async function loadRagStatus(projId: string) {
    try {
      ragStatus = await api.getRagStatus(projId);
    } catch (e) {
      ragStatus = null;
    }
  }

  async function handleIndexRag(forceFull: boolean = false) {
    if (!selectedProject) return;
    isRagIndexing = true;
    ragMsg = '';
    try {
      const res = await api.indexProjectRag(selectedProject.id, selectedProject.path, forceFull);
      ragMsg = `Indexed: ${res.files_scanned} files scanned, ${res.total_chunks} total chunks (${res.files_unchanged} unchanged).`;
      await loadRagStatus(selectedProject.id);
    } catch (e: any) {
      ragMsg = e.message || 'Indexing failed';
    } finally {
      isRagIndexing = false;
    }
  }

  async function handleSearchRag() {
    if (!selectedProject || !ragSearchQuery.trim()) {
      ragSearchResults = [];
      return;
    }
    isRagSearching = true;
    try {
      ragSearchResults = await api.searchRag(selectedProject.id, ragSearchQuery.trim());
    } catch (e) {
      ragSearchResults = [];
    } finally {
      isRagSearching = false;
    }
  }

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

  async function selectProject(proj: Project) {
    selectedProject = proj;
    activeDetailTab = 'overview';
    ragSearchResults = [];
    ragSearchQuery = '';
    ragMsg = '';
    await loadRagStatus(proj.id);
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

<main class="ml-56 pt-12 px-6 pb-6 min-h-[calc(100vh-48px)] bg-background flex flex-col flex-1 animate-page-enter">

  {#if selectedProject}
    <!-- PROJECT DETAIL VIEW -->
    <div class="space-y-3">
      <!-- Back Navigation Header -->
      <div class="pt-1 pb-1">
        <button
          onclick={backToProjectList}
          class="btn-ghost btn-sm group"
        >
          <span class="material-symbols-outlined text-[16px] group-hover:-translate-x-0.5 transition-transform">arrow_back</span>
          Back to Projects Browser
        </button>
      </div>

      <!-- Detail Header -->
      <header class="py-2.5 border-b border-outline-variant/50">
        <div class="flex items-center justify-between gap-3 mb-1">
          <div class="flex items-center gap-2.5">
            <span class="material-symbols-outlined text-primary text-2xl">folder_open</span>
            <div>
              <h1 class="font-headline-md text-[18px] font-semibold text-primary">{selectedProject.title}</h1>
              <p class="font-status-log text-[11px] text-on-surface-variant/80">{selectedProject.path}</p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            {#if selectedProject.git_repository}
              <span class="inline-flex items-center gap-1 bg-secondary-container/20 border border-secondary/30 text-secondary px-2 py-0.5 rounded-full font-label-caps text-[10px]">
                <span class="material-symbols-outlined text-[12px]">code_blocks</span>
                Git Repository
              </span>
            {/if}
          </div>
        </div>

        <!-- Language & Framework Pills -->
        <div class="flex items-center gap-1.5 flex-wrap mt-2">
          {#if (!selectedProject.languages || selectedProject.languages.length === 0) && (!selectedProject.frameworks || selectedProject.frameworks.length === 0)}
            <span class="bg-surface text-on-surface-variant/70 border border-outline-variant/50 px-2 py-0.5 rounded font-label-caps text-[10px] italic">
              Stack not detected
            </span>
          {:else}
            {#if selectedProject.languages}
              {#each selectedProject.languages as lang}
                <span class="bg-primary/10 border border-primary/20 text-primary px-2 py-0.5 rounded font-label-caps text-[10px]">
                  {lang}
                </span>
              {/each}
            {/if}
            {#if selectedProject.frameworks}
              {#each selectedProject.frameworks as fw}
                <span class="bg-surface-container-high border border-outline-variant/50 text-on-surface-variant px-2 py-0.5 rounded font-label-caps text-[10px]">
                  {fw}
                </span>
              {/each}
            {/if}
          {/if}
        </div>
      </header>

      <!-- Detail Tabs -->
      <nav class="flex items-center gap-3 border-b border-outline-variant/40 mb-3 select-none">
        {#each ['overview', 'files', 'research', 'tasks', 'context', 'automations'] as tab}
          <button
            onclick={() => activeDetailTab = tab as any}
            class="pb-1.5 font-ui-medium text-[12px] capitalize transition-colors relative flex items-center gap-1 px-0.5
              {activeDetailTab === tab ? 'text-primary border-b-2 border-secondary font-semibold' : 'text-on-surface-variant hover:text-primary'}"
          >
            {tab}
          </button>
        {/each}
      </nav>

      <!-- Tab Content Area -->
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 shadow-sm min-h-[260px]">
        {#if activeDetailTab === 'overview'}
          <div class="space-y-3">
            <h3 class="font-label-caps text-[11px] text-on-surface-variant/80 font-semibold tracking-wider">WORKSPACE CONTEXT</h3>
            <p class="font-ui-main text-[13px] text-on-surface leading-normal">
              {selectedProject.description || `Local repository configured at ${selectedProject.path}. This workspace context is active for Cocoa agent operations.`}
            </p>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
              <div class="p-2 bg-surface rounded-md border border-outline-variant/40">
                <div class="font-label-caps text-[10px] text-on-surface-variant mb-0.5">LAST MODIFIED</div>
                <div class="font-ui-medium text-[12px] text-primary">{formatTimeAgo(selectedProject.last_modified)}</div>
              </div>
              <div class="p-2 bg-surface rounded-md border border-outline-variant/40">
                <div class="font-label-caps text-[10px] text-on-surface-variant mb-0.5">LAST SCANNED</div>
                <div class="font-ui-medium text-[12px] text-primary">{formatTimeAgo(selectedProject.last_scanned)}</div>
              </div>
            </div>
          </div>
        {:else if activeDetailTab === 'context'}
          <div class="space-y-4">
            <!-- PROJECT RAG STATUS & CODE SEARCH CARD -->
            <div class="p-3 bg-surface rounded-md border border-outline-variant/50 space-y-2.5">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-[18px] text-primary">menu_book</span>
                  <div>
                    <h4 class="font-ui-medium text-[12px] text-primary font-semibold">Project RAG & Structural Knowledge</h4>
                    <p class="font-status-log text-[10px] text-on-surface-variant">Scope: {selectedProject.title} ({selectedProject.path || 'Workspace'})</p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    onclick={() => handleIndexRag(false)}
                    disabled={isRagIndexing}
                    class="bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 px-2.5 py-1 rounded font-ui-medium text-[11px] flex items-center gap-1 disabled:opacity-50 cursor-pointer"
                  >
                    <span class="material-symbols-outlined text-[13px] {isRagIndexing ? 'animate-spin' : ''}">sync</span>
                    {isRagIndexing ? 'Indexing...' : 'Index Project RAG'}
                  </button>
                  <button
                    onclick={() => handleIndexRag(true)}
                    disabled={isRagIndexing}
                    class="bg-surface border border-outline-variant/50 text-on-surface-variant hover:text-primary px-2 py-1 rounded font-ui-medium text-[10px] disabled:opacity-50 cursor-pointer"
                    title="Force rebuild all chunks"
                  >
                    Force Re-index
                  </button>
                </div>
              </div>

              <!-- RAG Status Metric Badges -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-status-log text-[10px]">
                <div class="bg-surface-container-low p-2 rounded border border-outline-variant/30">
                  <div class="text-on-surface-variant/70 mb-0.5">STATUS</div>
                  <div class="font-semibold text-primary flex items-center gap-1">
                    <span class="inline-block w-2 h-2 rounded-full {ragStatus?.indexing_status === 'INDEXED' ? 'bg-emerald-500' : 'bg-amber-500'}"></span>
                    {ragStatus?.indexing_status || 'IDLE'}
                  </div>
                </div>
                <div class="bg-surface-container-low p-2 rounded border border-outline-variant/30">
                  <div class="text-on-surface-variant/70 mb-0.5">INDEXED FILES</div>
                  <div class="font-semibold text-primary">{ragStatus?.total_files || 0} files</div>
                </div>
                <div class="bg-surface-container-low p-2 rounded border border-outline-variant/30">
                  <div class="text-on-surface-variant/70 mb-0.5">STRUCTURAL CHUNKS</div>
                  <div class="font-semibold text-primary">{ragStatus?.total_chunks || 0} chunks</div>
                </div>
                <div class="bg-surface-container-low p-2 rounded border border-outline-variant/30">
                  <div class="text-on-surface-variant/70 mb-0.5">VECTOR BACKEND</div>
                  <div class="font-semibold text-secondary truncate">{ragStatus?.vector_backend || 'INITIALIZING'}</div>
                </div>
              </div>

              {#if ragMsg}
                <div class="text-[11px] font-status-log text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2.5 py-1">
                  {ragMsg}
                </div>
              {/if}

              <!-- RAG Code & Symbol Search -->
              <div class="pt-1 space-y-2">
                <div class="flex items-center gap-2">
                  <div class="relative flex-1">
                    <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-on-surface-variant/60">code</span>
                    <input
                      type="text"
                      placeholder="Search code chunks (functions, classes, components, SQL)..."
                      bind:value={ragSearchQuery}
                      onkeydown={(e) => e.key === 'Enter' && handleSearchRag()}
                      class="w-full bg-surface-container-lowest border border-outline-variant/50 rounded-md pl-8 pr-3 py-1 font-ui-main text-[11px] text-primary focus:outline-none focus:border-secondary h-7"
                    />
                  </div>
                  <button
                    onclick={handleSearchRag}
                    disabled={isRagSearching}
                    class="btn-secondary h-7 text-[11px] px-2.5 py-0.5"
                  >
                    {isRagSearching ? 'Searching...' : 'Search Code'}
                  </button>
                </div>

                {#if ragSearchResults.length > 0}
                  <div class="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
                    {#each ragSearchResults as chunk}
                      <div class="p-2.5 bg-surface-container-lowest rounded border border-outline-variant/40 space-y-1">
                        <div class="flex items-center justify-between font-status-log text-[10px]">
                          <div class="flex items-center gap-1.5 truncate">
                            <span class="font-mono text-primary font-semibold truncate">{chunk.file_path}</span>
                            {#if chunk.symbol}
                              <span class="text-on-surface-variant">•</span>
                              <span class="font-mono text-secondary truncate">{chunk.symbol}</span>
                            {/if}
                          </div>
                          <div class="flex items-center gap-1.5 shrink-0">
                            <span class="px-1.5 py-0.2 bg-primary/10 text-primary rounded text-[9px] font-mono uppercase">{chunk.language}</span>
                            <span class="px-1.5 py-0.2 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded text-[9px] font-semibold">
                              {(chunk.relevance * 100).toFixed(0)}% match
                            </span>
                          </div>
                        </div>
                        <pre class="font-mono text-[11px] text-on-surface/90 bg-surface-container-low p-2 rounded overflow-x-auto max-h-32 leading-tight select-text">{chunk.content}</pre>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>

            <!-- AGENT SEMANTIC MEMORIES SECTION -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-outline-variant/40 pb-2 gap-2 pt-2">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-[18px] text-secondary">psychology</span>
                <h3 class="font-label-caps text-[11px] text-primary font-semibold tracking-wider uppercase">Agent Semantic Memory & Context</h3>
              </div>
              <div class="flex items-center gap-2">
                <button
                  onclick={handleRescanKnowledge}
                  disabled={isKnowledgeRescanning}
                  class="font-ui-medium text-[11px] text-secondary hover:underline flex items-center gap-1 cursor-pointer disabled:opacity-50"
                >
                  <span class="material-symbols-outlined text-[14px] {isKnowledgeRescanning ? 'animate-spin' : ''}">sync</span>
                  {isKnowledgeRescanning ? 'Indexing Graph...' : 'Index Knowledge Graph'}
                </button>
                <button
                  onclick={async () => {
                    try {
                      projectMemories = await api.getMemories(selectedProject?.id);
                    } catch {}
                  }}
                  class="font-ui-medium text-[11px] text-on-surface-variant hover:underline flex items-center gap-1 cursor-pointer"
                >
                  <span class="material-symbols-outlined text-[14px]">refresh</span>
                  Reload
                </button>
              </div>
            </div>

            <!-- Knowledge Hybrid Search Bar -->
            <div class="flex items-center gap-2">
              <div class="relative flex-1">
                <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-on-surface-variant/60">search</span>
                <input
                  type="text"
                  placeholder="Hybrid semantic memory search..."
                  bind:value={memorySearchQuery}
                  onkeydown={(e) => e.key === 'Enter' && handleSearchMemories()}
                  class="w-full bg-surface border border-outline-variant/50 rounded-md pl-8 pr-3 py-1.5 font-ui-main text-[12px] text-primary focus:outline-none focus:border-secondary"
                />
              </div>
              <button
                onclick={handleSearchMemories}
                class="bg-surface border border-outline-variant/50 hover:border-outline text-primary px-3 py-1.5 rounded-md font-ui-medium text-[11px] shadow-sm"
              >
                Search
              </button>
            </div>

            {#if projectMemories.length > 0}
              <div class="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                {#each projectMemories as mem}
                  <div class="p-3 bg-surface rounded-md border border-outline-variant/40 space-y-1.5">
                    <div class="flex items-center justify-between font-status-log text-[10px] text-on-surface-variant/70">
                      <div class="flex items-center gap-1.5">
                        <span class="font-mono text-secondary uppercase font-semibold">[{mem.memory_type}]</span>
                        <span class="px-1.5 py-0.5 rounded text-[9px] font-semibold tracking-wider uppercase
                          {mem.verification_status === 'VERIFIED' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' :
                           mem.verification_status === 'ACTIVE' ? 'bg-amber-50 text-amber-900 border border-amber-200' :
                           mem.verification_status === 'SUPERSEDED' ? 'bg-surface-variant text-on-surface-variant line-through opacity-70' :
                           'bg-surface-container text-on-surface-variant'}"
                        >
                          {mem.verification_status || 'ACTIVE'}
                        </span>
                      </div>
                      <div class="flex items-center gap-2">
                        <span>Importance: {mem.importance || 5}/10</span>
                        {#if mem.verification_status !== 'VERIFIED' && mem.verification_status !== 'SUPERSEDED'}
                          <button
                            onclick={() => handleVerifyMemory(mem.id)}
                            class="text-[10px] text-emerald-700 hover:underline font-semibold"
                          >
                            Verify
                          </button>
                        {/if}
                        {#if mem.verification_status !== 'ARCHIVED'}
                          <button
                            onclick={() => handleArchiveMemory(mem.id)}
                            class="text-[10px] text-on-surface-variant hover:underline"
                          >
                            Archive
                          </button>
                        {/if}
                      </div>
                    </div>
                    <p class="font-ui-main text-[12px] text-primary">{mem.content}</p>
                    <div class="flex items-center justify-between font-status-log text-[10px] text-on-surface-variant/50 pt-0.5">
                      <span>Source: {mem.source} ({mem.source_reliability || 'USER_CONFIRMED'})</span>
                      {#if mem.confidence}
                        <span>Confidence: {(mem.confidence * 100).toFixed(0)}%</span>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="p-6 text-center text-on-surface-variant/70 font-ui-main text-[12px]">
                No semantic memory entries stored for this project yet. Click "Index Knowledge Graph" or run tasks to populate persistent project context.
              </div>
            {/if}
          </div>
        {:else}
          <div class="text-center py-8 text-on-surface-variant font-ui-main text-[13px]">
            <span class="material-symbols-outlined text-3xl text-outline-variant mb-1 block">folder_open</span>
            <p class="capitalize">{activeDetailTab} workspace view active for {selectedProject.title}.</p>
          </div>
        {/if}
      </div>
    </div>
  {:else}

    <!-- PROJECTS LIST / REPOSITORY BROWSER -->
    <header class="py-2.5 border-b border-outline-variant/50 mb-3">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-2">
        <div>
          <h2 class="font-label-caps text-[10px] text-on-surface-variant/80 tracking-wider">LOCAL WORKSPACE BROWSER</h2>
          <h1 class="font-headline-md text-[18px] text-primary font-semibold">Projects</h1>
        </div>

        <div class="flex items-center gap-2">
          <button
            onclick={handleRescan}
            disabled={isScanning}
            class="btn-secondary disabled:opacity-50"
          >
            <span class="material-symbols-outlined text-[16px] {isScanning ? 'animate-spin' : ''}">sync</span>
            {isScanning ? 'Scanning...' : 'Rescan Workspace'}
          </button>

          <button
            onclick={openChangeModal}
            class="btn-primary"
          >
            <span class="material-symbols-outlined text-[16px]">folder</span>
            Change Folder
          </button>
        </div>
      </div>

      <!-- Current Workspace Banner -->
      <div class="flex items-center justify-between bg-surface-container-low border border-outline-variant/50 rounded-md px-3 py-1.5 font-status-log text-[11px] text-on-surface-variant">
        <div class="flex items-center gap-1.5 truncate">
          <span class="material-symbols-outlined text-[14px] text-secondary">folder_managed</span>
          <span class="font-medium text-primary">Your workspace:</span>
          <span class="truncate">{workspace?.path || '~/Projects'}</span>
        </div>
        <span class="text-[11px] opacity-75">{filteredProjects.length} Projects Discovered</span>
      </div>
    </header>

    <!-- Search & Filter Control Bar -->
    <div class="flex flex-col sm:flex-row items-center justify-between gap-3 mb-3">
      <!-- Search Input -->
      <div class="relative w-full sm:w-80">
        <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-[16px]">search</span>
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search projects..."
          class="w-full bg-surface-container-lowest border border-outline-variant/50 rounded-md pl-8 pr-3 py-1 font-ui-main text-[12px] text-primary placeholder:text-on-surface-variant/60 focus:border-secondary focus:outline-none transition-colors h-8"
        />
      </div>

      <!-- Sort Controls -->
      <div class="flex items-center gap-1.5 self-end sm:self-auto font-ui-medium text-[12px] text-on-surface-variant select-none">
        <span>Sort:</span>
        <select
          bind:value={sortBy}
          class="bg-surface-container-lowest border border-outline-variant/50 rounded-md px-2 py-1 text-primary font-ui-medium focus:outline-none h-8 text-[12px]"
        >
          <option value="recent">Recently Modified</option>
          <option value="alphabetical">Alphabetical</option>
        </select>
      </div>
    </div>

    <!-- UI STATES -->
    {#if isLoading || isScanning}
      <div class="flex-1 flex flex-col items-center justify-center py-12 text-on-surface-variant animate-pulse font-ui-main text-[13px]">
        <span class="material-symbols-outlined text-3xl mb-2 animate-spin">sync</span>
        <p>Scanning workspace...</p>
      </div>
    {:else if errorMsg}
      <div class="bg-error/10 border border-error/20 text-error rounded-md p-3 font-ui-main my-3 text-center text-[13px]">
        <span class="material-symbols-outlined text-xl mb-0.5">warning</span>
        <p>{errorMsg}</p>
      </div>
    {:else if filteredProjects.length === 0}
      <!-- Empty State -->
      <div class="flex-1 flex flex-col items-center justify-center py-12">
        <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-8 text-center max-w-md shadow-sm">
          <span class="material-symbols-outlined text-4xl text-outline-variant mb-2">manage_search</span>
          <h3 class="font-headline-md text-[18px] text-primary mb-1 font-semibold">No projects found</h3>
          <p class="font-ui-main text-[13px] text-on-surface-variant mb-4">
            No project markers (`package.json`, `pyproject.toml`, `Cargo.toml`, `.git`, etc.) were discovered inside <span class="font-status-log text-[11px]">{workspace?.path || '~/Projects'}</span>.
          </p>
          <button
            onclick={openChangeModal}
            class="bg-primary text-on-primary hover:bg-primary-container px-3.5 py-1.5 rounded-full font-ui-medium text-[12px] inline-flex items-center gap-1 shadow-sm transition-colors"
          >
            <span class="material-symbols-outlined text-[16px]">folder</span>
            Select Another Workspace Directory
          </button>
        </div>
      </div>
    {:else}
      <!-- PROJECT CARDS GRID -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5 w-full flex-1">
        {#each filteredProjects as proj}
          <div
            onclick={() => selectProject(proj)}
            onkeydown={(e) => e.key === 'Enter' && selectProject(proj)}
            role="button"
            tabindex={0}
            class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3 hover:border-secondary transition-all cursor-pointer flex flex-col justify-between group shadow-sm"
          >
            <div>
              <!-- Top Row: Name & Git Badge -->
              <div class="flex items-start justify-between gap-2 mb-1">
                <h3 class="font-ui-medium text-[13px] font-medium text-primary group-hover:text-secondary transition-colors flex items-center gap-1.5 truncate">
                  <span class="material-symbols-outlined text-primary group-hover:text-secondary text-[18px]">folder_open</span>
                  {proj.title}
                </h3>

                {#if proj.git_repository}
                  <span class="inline-flex items-center gap-0.5 bg-secondary-container/20 text-secondary border border-secondary/30 px-1.5 py-0.5 rounded font-label-caps text-[10px] shrink-0">
                    <span class="material-symbols-outlined text-[11px]">code_blocks</span>
                    Git
                  </span>
                {/if}
              </div>

              <!-- Subtitle Path -->
              <p class="font-status-log text-[11px] text-on-surface-variant/70 mb-2 truncate">
                {proj.path}
              </p>

              <!-- Language & Framework Tags -->
              <div class="flex items-center gap-1 flex-wrap mb-2">
                {#if (!proj.languages || proj.languages.length === 0) && (!proj.frameworks || proj.frameworks.length === 0)}
                  <span class="bg-surface text-on-surface-variant/70 border border-outline-variant/50 px-1.5 py-0.5 rounded font-label-caps text-[10px] italic">
                    Stack not detected
                  </span>
                {:else}
                  {#if proj.languages}
                    {#each proj.languages as lang}
                      <span class="bg-surface-container-high text-primary border border-outline-variant/50 px-1.5 py-0.5 rounded font-label-caps text-[10px]">
                        {lang}
                      </span>
                    {/each}
                  {/if}

                  {#if proj.frameworks}
                    {#each proj.frameworks as fw}
                      <span class="bg-surface text-on-surface-variant border border-outline-variant/50 px-1.5 py-0.5 rounded font-label-caps text-[10px]">
                        {fw}
                      </span>
                    {/each}
                  {/if}
                {/if}
              </div>
            </div>

            <!-- Footer: Last Modified -->
            <div class="pt-1.5 border-t border-outline-variant/40 flex items-center justify-between text-on-surface-variant/70 font-status-log text-[10px]">
              <span>Updated {formatTimeAgo(proj.last_modified)}</span>
              <span class="material-symbols-outlined text-[14px] group-hover:translate-x-0.5 transition-transform">chevron_right</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}

  {/if}

  <!-- CHANGE WORKSPACE MODAL -->
  {#if showChangeWorkspaceModal}
    <div class="fixed inset-0 bg-primary/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 max-w-md w-full shadow-lg space-y-3">
        <div class="flex items-center justify-between border-b border-outline-variant/40 pb-2">
          <h3 class="font-headline-md text-[16px] font-semibold text-primary">Select Workspace Directory</h3>
          <button
            onclick={() => showChangeWorkspaceModal = false}
            disabled={modalIsScanning}
            class="text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
          >
            <span class="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        <p class="font-ui-main text-[12px] text-on-surface-variant leading-normal">
          Enter the absolute path to your root project directory (e.g. <span class="font-status-log text-[11px]">/home/rev/My Personal Space/Projects</span>). Cocoa will automatically discover all project repositories inside.
        </p>

        {#if modalErrorMsg}
          <div class="bg-error/10 border border-error/20 text-error rounded-md p-2 font-ui-main text-[12px] flex items-center gap-1">
            <span class="material-symbols-outlined text-[16px]">error</span>
            <span>{modalErrorMsg}</span>
          </div>
        {/if}

        <div>
          <label for="workspace-path-input" class="font-ui-medium text-[12px] text-primary block mb-1">Workspace Directory Path</label>
          <input
            id="workspace-path-input"
            type="text"
            bind:value={newWorkspacePath}
            disabled={modalIsScanning}
            placeholder="/home/user/Projects"
            class="w-full bg-surface border border-outline-variant/50 rounded-md px-3 py-1 font-status-log text-[11px] text-primary focus:border-secondary focus:outline-none transition-colors disabled:opacity-50 h-8"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-2">
          <button
            onclick={() => showChangeWorkspaceModal = false}
            disabled={modalIsScanning}
            class="btn-secondary disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onclick={handleSetWorkspace}
            disabled={modalIsScanning}
            class="btn-primary disabled:opacity-50"
          >
            {#if modalIsScanning}
              <span class="material-symbols-outlined text-[16px] animate-spin">sync</span>
              Scanning...
            {:else}
              Scan & Save
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}

</main>
