<script lang="ts">
  // Projects placeholder — shell consistent with other views
</script>

<main class="ml-64 pt-24 px-margin-desktop pb-xxl">
  <div class="max-w-[900px]">
    <div class="mb-xl">
      <h2 class="font-label-caps text-label-caps text-on-surface-variant mb-xs">YOUR WORKSPACE</h2>
      <h1 class="font-display-lg text-display-lg text-primary">Projects</h1>
    </div>

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
  </div>
</main>
