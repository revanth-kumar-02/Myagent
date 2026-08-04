<script lang="ts">
  import { mockPlan, mockActivity } from '$lib/api/mock';
</script>

<!-- Full-viewport layout offset by sidebar + topbar -->
<main class="ml-64 pt-16 px-margin-desktop pb-margin-desktop h-screen overflow-hidden flex flex-col">

  <!-- Header row -->
  <div class="flex justify-between items-end py-md mb-lg border-b border-outline-variant shrink-0">
    <div>
      <p class="font-label-caps text-label-caps text-on-surface-variant mb-xs">Active Task</p>
      <h2 class="font-display-lg text-display-lg text-primary truncate max-w-4xl">Research the best database for Project X</h2>
    </div>
    <div class="flex items-center gap-sm bg-secondary-container/20 px-md py-sm rounded-full border border-secondary/20 shadow-[0_0_24px_rgba(119,87,81,0.05)] shrink-0 ml-lg">
      <span class="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
      <span class="font-label-caps text-label-caps text-secondary">Running</span>
    </div>
  </div>

  <!-- 3-column workspace -->
  <div class="grid grid-cols-12 gap-gutter flex-1 overflow-hidden min-h-0">

    <!-- Column 1: PLAN -->
    <section class="col-span-3 flex flex-col overflow-hidden">
      <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md flex items-center gap-sm shrink-0">
        <span class="material-symbols-outlined text-sm">flag</span>
        PLAN
      </h3>
      <div class="bg-surface-container-lowest rounded-lg border border-outline-variant p-md flex-1 overflow-y-auto shadow-[0_4px_24px_rgba(106,91,90,0.04)]">
        <ul class="space-y-sm">
          {#each mockPlan as step}
            <li class="flex items-start gap-sm p-sm rounded transition-colors group
              {step.status === 'active' ? 'bg-surface-container-low border-l-2 border-secondary relative overflow-hidden' : 'hover:bg-surface-container-low'}">
              {#if step.status === 'active'}
                <div class="absolute inset-0 bg-gradient-to-r from-secondary/5 to-transparent pointer-events-none"></div>
              {/if}
              {#if step.status === 'done'}
                <span class="material-symbols-outlined text-secondary-fixed-dim shrink-0 mt-xs">check_circle</span>
                <span class="font-ui-main text-ui-main text-on-surface-variant line-through opacity-70">{step.label}</span>
              {:else if step.status === 'active'}
                <span class="material-symbols-outlined text-secondary shrink-0 mt-xs relative z-10">arrow_forward</span>
                <span class="font-ui-medium text-ui-medium text-primary relative z-10">{step.label}</span>
              {:else}
                <span class="material-symbols-outlined text-outline shrink-0 mt-xs">radio_button_unchecked</span>
                <span class="font-ui-main text-ui-main text-on-surface">{step.label}</span>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    </section>

    <!-- Column 2: ACTIVITY (dark cocoa terminal) -->
    <section class="col-span-5 flex flex-col overflow-hidden pl-md border-l border-outline-variant/50">
      <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md flex items-center gap-sm shrink-0">
        <span class="material-symbols-outlined text-sm">history</span>
        ACTIVITY
      </h3>
      <div class="bg-[#352928] rounded-lg p-md flex-1 overflow-y-auto shadow-inner border border-[#1f1514]/20 relative">
        <div class="absolute top-0 right-0 p-sm opacity-30">
          <span class="material-symbols-outlined text-on-primary-container text-2xl">terminal</span>
        </div>
        <div class="space-y-3 font-status-log text-status-log text-[#a18f8e]">
          {#each mockActivity as entry}
            {#if entry.status === 'active'}
              <div class="flex gap-md items-start relative bg-[#1f1514]/30 p-sm rounded -mx-sm">
                <div class="absolute left-0 top-0 bottom-0 w-1 bg-[#775751] rounded-l"></div>
                <span class="text-[#ffdad4] shrink-0 font-medium">[{entry.time}]</span>
                <div class="text-[#ffffff]">
                  <span class="text-[#ffdad4] mr-sm animate-pulse">⟳</span>
                  <span>{entry.message}</span>
                  {#if entry.details}
                    <div class="mt-xs pl-lg text-[11px] opacity-70 space-y-xs font-mono">
                      {#each entry.details as detail}
                        <p>{detail}</p>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>
            {:else}
              <div class="flex gap-md items-start">
                <span class="text-[#e7bdb6] shrink-0 opacity-70">[{entry.time}]</span>
                <div>
                  <span class="text-[#f3dedc] mr-sm">✓</span>
                  <span>{entry.message}</span>
                </div>
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </section>

    <!-- Column 3: RESULT -->
    <section class="col-span-4 flex flex-col overflow-hidden pl-md border-l border-outline-variant/50">
      <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md flex items-center gap-sm shrink-0">
        <span class="material-symbols-outlined text-sm">article</span>
        RESULT
      </h3>
      <div class="bg-surface-container-lowest rounded-lg border border-outline-variant p-xl flex-1 flex flex-col items-center justify-center text-center shadow-[0_4px_24px_rgba(106,91,90,0.04)] relative overflow-hidden">
        <div class="absolute top-0 right-0 w-32 h-32 bg-secondary/5 rounded-bl-full pointer-events-none"></div>
        <div class="absolute bottom-0 left-0 w-24 h-24 bg-primary/5 rounded-tr-full pointer-events-none"></div>
        <div class="mb-lg relative">
          <div class="absolute inset-0 bg-secondary/20 rounded-full blur-xl animate-pulse"></div>
          <span class="material-symbols-outlined text-5xl text-outline-variant relative z-10">hourglass_empty</span>
        </div>
        <h4 class="font-headline-md text-headline-md text-on-surface mb-sm">Analysis in progress...</h4>
        <p class="font-body-reading text-body-reading text-on-surface-variant max-w-sm">
          Findings will appear here once verified and formalized into a recommendation.
        </p>
        <button
          disabled
          class="mt-xl text-on-surface-variant font-ui-medium text-ui-medium px-md py-sm rounded border border-transparent opacity-50 cursor-not-allowed"
        >
          View Draft (Unavailable)
        </button>
      </div>
    </section>

  </div>
</main>
