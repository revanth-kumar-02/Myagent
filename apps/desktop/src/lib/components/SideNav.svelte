<script lang="ts">
  import { currentRoute, navigate, type Route } from '$lib/stores/navigation';

  type NavItem = {
    id: Route;
    label: string;
    icon: string;
  };

  const navItems: NavItem[] = [
    { id: 'home',        label: 'Home',        icon: 'home'           },
    { id: 'projects',    label: 'Projects',    icon: 'folder_open'    },
    { id: 'research',    label: 'Research',    icon: 'travel_explore' },
    { id: 'tasks',       label: 'Tasks',       icon: 'checklist'      },
    { id: 'automations', label: 'Automations', icon: 'auto_mode'      },
  ];
</script>

<nav class="h-screen w-64 fixed left-0 top-0 bg-surface border-r border-outline-variant flex flex-col py-xl px-md z-20">
  <!-- Brand -->
  <div class="mb-xxl flex items-center gap-md">
    <div class="w-10 h-10 rounded-full bg-primary-container flex items-center justify-center shrink-0">
      <span class="material-symbols-outlined text-on-primary-container fill text-[20px]">psychology</span>
    </div>
    <div>
      <h1 class="font-headline-md text-headline-md text-primary leading-tight tracking-tight">Cocoa</h1>
      <p class="font-label-caps text-label-caps text-on-surface-variant opacity-70 mt-xs">Quiet Intelligence</p>
    </div>
  </div>

  <!-- Nav links -->
  <ul class="flex flex-col gap-xs flex-grow">
    {#each navItems as item}
      {@const active = $currentRoute === item.id}
      <li>
        <button
          onclick={() => navigate(item.id)}
          class="
            w-full flex items-center gap-md py-sm px-sm rounded-lg transition-all duration-200 cursor-pointer
            {active
              ? 'text-primary font-semibold border-r-2 border-secondary bg-surface-container-low'
              : 'text-on-surface-variant opacity-70 hover:bg-surface-container-low hover:opacity-100'}
          "
        >
          <span class="material-symbols-outlined {active ? 'fill' : ''}">{item.icon}</span>
          <span class="{active ? 'font-ui-medium text-ui-medium' : 'font-ui-main text-ui-main'}">{item.label}</span>
        </button>
      </li>
    {/each}
  </ul>

  <!-- Bottom: Settings + New Request -->
  <div class="mt-auto pt-lg border-t border-outline-variant flex flex-col gap-sm">
    <button
      onclick={() => navigate('settings')}
      class="
        flex items-center gap-md py-sm px-sm rounded-lg transition-all duration-200
        {$currentRoute === 'settings'
          ? 'text-primary font-semibold border-r-2 border-secondary bg-surface-container-low'
          : 'text-on-surface-variant opacity-70 hover:bg-surface-container-low hover:opacity-100'}
      "
    >
      <span class="material-symbols-outlined">settings</span>
      <span class="font-ui-main text-ui-main">Settings</span>
    </button>

    <button
      class="w-full mt-md bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary-container transition-colors py-sm px-md rounded-lg font-ui-medium text-ui-medium flex items-center justify-center gap-xs shadow-sm"
    >
      <span class="material-symbols-outlined text-[18px]">add</span>
      New Request
    </button>
  </div>
</nav>
