<script lang="ts">
  export let title: string = 'Cocoa Agent';
  export let showHomeSubnav: boolean = false;
</script>

<header class="fixed top-0 left-64 right-0 h-16 bg-background flex justify-between items-center px-margin-desktop z-10 border-b border-outline-variant/30">
  <div class="flex items-center gap-xl">
    <span class="font-headline-md text-headline-md text-primary tracking-tight">{title}</span>

    {#if showHomeSubnav}
      <nav class="hidden md:flex items-center gap-lg border-l border-outline-variant pl-lg h-8">
        <a class="text-secondary font-semibold font-ui-medium text-ui-medium" href="#">Planning</a>
        <a class="text-on-surface-variant font-ui-medium text-ui-medium hover:text-primary transition-colors" href="#">Researching</a>
        <a class="text-on-surface-variant font-ui-medium text-ui-medium hover:text-primary transition-colors" href="#">Verifying</a>
      </nav>
    {/if}
  </div>

  <div class="flex items-center gap-md text-on-surface-variant">
    <button class="hover:text-primary transition-colors p-xs rounded-full hover:bg-surface-container-low">
      <span class="material-symbols-outlined">notifications</span>
    </button>
    <button class="hover:text-primary transition-colors p-xs rounded-full hover:bg-surface-container-low">
      <span class="material-symbols-outlined">account_circle</span>
    </button>
  </div>
</header>
