<script lang="ts">
  import { mockAutomationNodes, mockLastRun } from '$lib/api/mock';

  const iconMap: Record<string, string> = {
    trigger: 'schedule',
    agent:   'smart_toy',
    notify:  'mark_email_unread',
  };
</script>

<main class="ml-64 pt-16 min-h-screen bg-background">
  <div class="px-margin-desktop pt-lg max-w-4xl mx-auto pb-xxl">

    <!-- Automation header -->
    <header class="mb-xl flex justify-between items-end border-b border-outline-variant pb-lg">
      <div>
        <h2 class="font-display-lg text-display-lg text-primary mb-2">Weekly Project Check</h2>
        <p class="font-ui-main text-ui-main text-on-surface-variant">
          "Every Sunday, check my project and tell me if anything needs my attention."
        </p>
      </div>
      <div class="flex items-center gap-4 shrink-0 ml-lg">
        <span class="bg-secondary-fixed text-on-secondary-fixed px-3 py-1 rounded-full font-label-caps text-label-caps flex items-center gap-1">
          <span class="material-symbols-outlined text-[14px]">play_arrow</span> Active
        </span>
        <button class="text-on-surface-variant hover:text-primary border border-outline-variant rounded px-3 py-1 font-ui-main text-ui-main transition-colors">Edit</button>
      </div>
    </header>

    <!-- Node flow canvas -->
    <div class="relative py-xl flex flex-col items-center">
      <!-- Vertical connector line -->
      <div class="absolute top-0 bottom-0 left-1/2 -ml-px w-0.5 bg-surface-container-highest z-0"></div>

      {#each mockAutomationNodes as node, i}
        <div class="relative z-10 flex flex-col items-center {i < mockAutomationNodes.length - 1 ? 'mb-xxl' : ''} w-full max-w-{node.type === 'agent' ? 'lg' : 'md'}">
          <div class="bg-surface-container-lowest border border-surface-tint rounded-lg p-{node.type === 'agent' ? 'lg' : 'md'} w-full shadow-[0_8px_24px_rgba(53,41,40,0.04)] hover:border-outline-variant transition-colors max-w-lg">
            <div class="flex items-start gap-4 {node.type === 'agent' ? 'mb-md pb-md border-b border-surface-container-highest' : ''}">
              <div class="bg-surface-container-low p-2 rounded text-secondary shrink-0">
                <span class="material-symbols-outlined text-[24px]">{iconMap[node.type]}</span>
              </div>
              <div class="flex-1">
                <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-1">{node.detail}</h3>
                <div class="font-ui-medium text-ui-medium text-primary">{node.label}</div>
                <div class="font-ui-main text-ui-main text-on-surface-variant mt-1 text-[13px]">{node.sublabel}</div>
              </div>
            </div>
            {#if node.steps}
              <div class="space-y-3">
                {#each node.steps as step}
                  <div class="flex items-center gap-3 text-on-surface font-ui-main text-ui-main">
                    <span class="material-symbols-outlined text-outline-variant text-[18px]">check_circle</span>
                    {step}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
          <!-- Connector dot (not on last node) -->
          {#if i < mockAutomationNodes.length - 1}
            <div class="w-3 h-3 rounded-full bg-surface-tint absolute -bottom-6 border-2 border-background"></div>
          {/if}
        </div>
      {/each}

      <!-- Terminal marker -->
      <div class="w-4 h-4 rounded-sm bg-outline-variant absolute -bottom-8 border-2 border-background z-10"></div>
    </div>

    <!-- Last run info -->
    <div class="mt-xl flex justify-center">
      <div class="bg-surface-container-high rounded p-md inline-flex items-center gap-4 border border-outline-variant">
        <span class="material-symbols-outlined text-on-surface-variant">history</span>
        <div class="font-status-log text-status-log text-on-surface-variant">
          Last Run: <span class="text-primary font-medium">{mockLastRun.date}</span><br/>
          Result: <span class="text-primary">{mockLastRun.result}</span>
        </div>
      </div>
    </div>

  </div>
</main>
