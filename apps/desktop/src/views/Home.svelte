<script lang="ts">
  import StatusChip from '$lib/components/StatusChip.svelte';
  import { mockActiveTask, mockRecentProjects } from '$lib/api/mock';

  let commandText = '';

  function autoResize(event: Event) {
    const el = event.target as HTMLTextAreaElement;
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
  }
</script>

<!-- Main content offset by fixed sidebar + topbar -->
<main class="ml-64 pt-24 px-margin-desktop pb-xxl w-full flex-1">
  <div class="max-w-[720px] mx-auto w-full">

    <!-- Command Input -->
    <section class="mb-xxl mt-lg">
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg shadow-[0_8px_24px_rgba(53,41,40,0.04)] relative focus-within:border-secondary focus-within:shadow-[0_8px_32px_rgba(119,87,81,0.08)] transition-all duration-300">
        <textarea
          bind:value={commandText}
          on:input={autoResize}
          placeholder="Ask your agent to research, analyze, organize, or act..."
          rows="2"
          class="w-full bg-transparent border-none outline-none font-ui-medium text-[20px] leading-[30px] text-primary placeholder:text-on-surface-variant/50 resize-none py-xs focus:ring-0"
        ></textarea>

        <div class="mt-xl flex items-center justify-between border-t border-outline-variant pt-md">
          <!-- Utilities -->
          <div class="flex items-center gap-md">
            <button class="flex items-center gap-xs text-on-surface-variant hover:text-primary hover:bg-surface-container-low px-sm py-xs rounded transition-colors font-ui-medium text-ui-medium">
              <span class="material-symbols-outlined text-[18px]">attach_file</span>
              + File
            </button>
            <button class="flex items-center gap-xs text-on-surface-variant border border-outline-variant hover:border-outline hover:bg-surface-container-low px-md py-[6px] rounded-full transition-colors font-label-caps text-label-caps">
              <span class="material-symbols-outlined text-[16px]">folder_open</span>
              Project: Global Strategy
              <span class="material-symbols-outlined text-[16px] ml-xs">arrow_drop_down</span>
            </button>
          </div>
          <!-- Run -->
          <button class="bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary-container px-lg py-sm rounded-full font-ui-medium text-ui-medium flex items-center gap-xs transition-colors shadow-sm group">
            Run
            <span class="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">arrow_forward</span>
          </button>
        </div>
      </div>
    </section>

    <!-- Active Work -->
    <section class="mb-xl">
      <h2 class="font-label-caps text-label-caps text-on-surface-variant mb-md tracking-wider">Active Work</h2>
      <div class="bg-surface border border-outline-variant rounded-lg p-lg flex items-center justify-between hover:bg-surface-container-lowest transition-colors cursor-pointer group">
        <div class="flex items-center gap-md">
          <div class="w-10 h-10 rounded bg-surface-container-high flex items-center justify-center text-on-surface-variant group-hover:text-primary transition-colors">
            <span class="material-symbols-outlined">{mockActiveTask.icon}</span>
          </div>
          <div>
            <h3 class="font-ui-medium text-ui-medium text-primary">{mockActiveTask.title}</h3>
            <p class="font-ui-main text-[13px] text-on-surface-variant mt-xs">{mockActiveTask.description}</p>
          </div>
        </div>
        <StatusChip status={mockActiveTask.status} />
      </div>
    </section>

    <!-- Recent Projects -->
    <section>
      <h2 class="font-label-caps text-label-caps text-on-surface-variant mb-md tracking-wider">Recent Projects</h2>
      <div class="grid grid-cols-3 gap-lg">
        {#each mockRecentProjects as project}
          <div class="bg-surface-container-low border border-outline-variant rounded-lg p-md hover:bg-surface-container-lowest hover:border-outline hover:shadow-[0_4px_12px_rgba(53,41,40,0.03)] transition-all duration-300 cursor-pointer flex flex-col justify-between h-32 group">
            <div class="flex items-center justify-between text-on-surface-variant">
              <span class="material-symbols-outlined text-[20px] group-hover:text-primary transition-colors">{project.icon}</span>
              <span class="font-status-log text-code-sm opacity-60">{project.ago}</span>
            </div>
            <h3 class="font-ui-medium text-ui-medium text-primary">{project.title}</h3>
          </div>
        {/each}
      </div>
    </section>

  </div>
</main>
