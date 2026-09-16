<script lang="ts">
  import { currentRoute, navigate, type Route } from '$lib/stores/navigation';

  type NavItem = {
    id: Route;
    label: string;
    icon: string;
  };

  const navItems: NavItem[] = [
    { id: 'home',        label: 'Home',        icon: 'home'           },
    { id: 'tasks',       label: 'Tasks',       icon: 'checklist'      },
    { id: 'projects',    label: 'Projects',    icon: 'folder_open'    },
    { id: 'research',    label: 'Research',    icon: 'travel_explore' },
    { id: 'activity',    label: 'Activity',    icon: 'history'        },
    { id: 'diagnostics', label: 'Diagnostics', icon: 'health_and_safety' },
    { id: 'automations', label: 'Automations', icon: 'auto_mode'      },
  ];
</script>

<nav class="h-screen w-56 fixed left-0 top-0 bg-surface border-r border-outline-variant/60 flex flex-col py-4 px-3 z-20 select-none">
  <!-- Brand -->
  <div class="mb-4 flex items-center gap-2.5 px-1">
    <div class="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center shrink-0 shadow-sm transition-transform duration-200 hover:scale-105">
      <span class="material-symbols-outlined text-on-primary-container fill text-[18px]">psychology</span>
    </div>
    <div>
      <h1 class="font-headline-md text-[18px] text-primary leading-tight tracking-tight font-semibold">Cocoa</h1>
      <p class="font-label-caps text-[10px] text-on-surface-variant opacity-70 tracking-wider">QUIET INTELLIGENCE</p>
    </div>
  </div>

  <!-- Nav links -->
  <ul class="flex flex-col gap-0.5 flex-grow overflow-y-auto">
    {#each navItems as item}
      {@const active = $currentRoute === item.id}
      <li>
        <button
          onclick={() => navigate(item.id)}
          class="
            w-full flex items-center gap-2.5 py-1.5 px-2.5 rounded-md transition-all duration-200 cursor-pointer text-xs active:scale-[0.98]
            {active
              ? 'text-primary font-semibold border-r-2 border-secondary bg-surface-container-low shadow-2xs'
              : 'text-on-surface-variant opacity-75 hover:bg-surface-container-low hover:opacity-100 hover:translate-x-0.5'}
          "
        >
          <span class="material-symbols-outlined text-[18px] transition-transform duration-150 {active ? 'fill scale-105' : ''}">{item.icon}</span>
          <span class="font-ui-medium text-[13px]">{item.label}</span>
        </button>
      </li>
    {/each}
  </ul>

  <!-- Bottom: Settings + New Request -->
  <div class="mt-auto pt-3 border-t border-outline-variant/50 flex flex-col gap-1.5">
    <button
      onclick={() => navigate('settings')}
      class="
        w-full flex items-center gap-2.5 py-1.5 px-2.5 rounded-md transition-all duration-200 text-xs active:scale-[0.98]
        {$currentRoute === 'settings'
          ? 'text-primary font-semibold border-r-2 border-secondary bg-surface-container-low'
          : 'text-on-surface-variant opacity-75 hover:bg-surface-container-low hover:opacity-100 hover:translate-x-0.5'}
      "
    >
      <span class="material-symbols-outlined text-[18px]">settings</span>
      <span class="font-ui-main text-[13px]">Settings</span>
    </button>

    <button
      onclick={() => navigate('home')}
      class="btn-primary w-full mt-1 flex items-center justify-center gap-1.5"
    >
      <span class="material-symbols-outlined text-[16px]">add</span>
      New Request
    </button>
  </div>
</nav>
