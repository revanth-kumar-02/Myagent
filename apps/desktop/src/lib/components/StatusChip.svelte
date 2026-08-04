<script lang="ts">
  export let status: 'running' | 'idle' | 'error' | 'done' = 'idle';
</script>

{#if status === 'running'}
  <div class="flex items-center gap-sm bg-secondary/10 border border-secondary/20 px-md py-[6px] rounded-full">
    <span class="relative flex h-2.5 w-2.5">
      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75"></span>
      <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-secondary"></span>
    </span>
    <span class="font-label-caps text-label-caps text-secondary">Running</span>
  </div>
{:else if status === 'idle'}
  <div class="flex items-center gap-sm bg-outline-variant/30 border border-outline-variant px-md py-[6px] rounded-full">
    <span class="w-2.5 h-2.5 rounded-full bg-outline-variant"></span>
    <span class="font-label-caps text-label-caps text-on-surface-variant">Idle</span>
  </div>
{:else if status === 'error'}
  <div class="flex items-center gap-sm bg-error/10 border border-error/20 px-md py-[6px] rounded-full">
    <span class="w-2.5 h-2.5 rounded-full bg-error"></span>
    <span class="font-label-caps text-label-caps text-error">Error</span>
  </div>
{:else if status === 'done'}
  <div class="flex items-center gap-sm bg-secondary-container/30 border border-secondary-fixed-dim/30 px-md py-[6px] rounded-full">
    <span class="w-2.5 h-2.5 rounded-full bg-secondary-fixed-dim"></span>
    <span class="font-label-caps text-label-caps text-on-secondary-container">Done</span>
  </div>
{/if}
