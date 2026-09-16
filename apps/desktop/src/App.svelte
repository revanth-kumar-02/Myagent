<script lang="ts">
  import './app.css';
  import { currentRoute } from '$lib/stores/navigation';
  import SideNav from '$lib/components/SideNav.svelte';
  import TopBar from '$lib/components/TopBar.svelte';

  import Home from './views/Home.svelte';
  import Projects from './views/Projects.svelte';
  import Research from './views/Research.svelte';
  import Tasks from './views/Tasks.svelte';
  import Activity from './views/Activity.svelte';
  import Diagnostics from './views/Diagnostics.svelte';
  import Automations from './views/Automations.svelte';
  import Settings from './views/Settings.svelte';

  const titles: Record<string, string> = {
    home:        'Cocoa Agent',
    projects:    'Projects',
    tasks:       'Task Workspace',
    activity:    'Activity Center',
    diagnostics: 'System Health & Diagnostics',
    automations: 'Automations',
    settings:    'Settings',
  };
</script>

<div class="flex min-h-screen bg-background antialiased">
  <SideNav />

  {#if $currentRoute === 'research'}
    <Research />
  {:else if $currentRoute === 'tasks'}
    <Tasks />
  {:else if $currentRoute === 'activity'}
    <Activity />
  {:else if $currentRoute === 'diagnostics'}
    <Diagnostics />
  {:else}
    <TopBar title={titles[$currentRoute] ?? 'Cocoa Agent'} showHomeSubnav={$currentRoute === 'home'} />
    {#if $currentRoute === 'home'}
      <Home />
    {:else if $currentRoute === 'projects'}
      <Projects />
    {:else if $currentRoute === 'automations'}
      <Automations />
    {:else if $currentRoute === 'settings'}
      <Settings />
    {/if}
  {/if}
</div>
