<script lang="ts">
  export let title: string = 'Cocoa Agent';
  export let showHomeSubnav: boolean = false;
</script>

<header class="fixed top-0 left-56 right-0 h-12 bg-background flex justify-between items-center px-4 z-10 border-b border-outline-variant/40 select-none">
  <div class="flex items-center gap-4">
    <span class="font-headline-md text-[16px] text-primary font-semibold tracking-tight">{title}</span>

    {#if showHomeSubnav}
      <nav class="hidden md:flex items-center gap-3 border-l border-outline-variant/40 pl-3 h-5">
        <a class="text-secondary font-semibold font-ui-medium text-[12px]" href="#planning">Planning</a>
        <a class="text-on-surface-variant font-ui-medium text-[12px] hover:text-primary transition-colors" href="#researching">Researching</a>
        <a class="text-on-surface-variant font-ui-medium text-[12px] hover:text-primary transition-colors" href="#verifying">Verifying</a>
      </nav>
    {/if}
  </div>

  <div class="flex items-center gap-2 text-on-surface-variant">
    <button class="hover:text-primary transition-colors p-1 rounded-md hover:bg-surface-container-low" title="Notifications">
      <span class="material-symbols-outlined text-[18px]">notifications</span>
    </button>
    <button class="hover:text-primary transition-colors p-1 rounded-md hover:bg-surface-container-low" title="Account">
      <span class="material-symbols-outlined text-[18px]">account_circle</span>
    </button>
  </div>
</header>
