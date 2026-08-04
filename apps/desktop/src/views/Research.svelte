<script lang="ts">
  import { mockSources } from '$lib/api/mock';

  const investigationPlan = [
    { label: 'Material Analysis',  pct: 100, status: 'done'    },
    { label: 'Passive Cooling Tech', pct: 65,  status: 'running' },
    { label: 'Regulatory Impact',  pct: 0,   status: 'pending' },
  ];
</script>

<div class="ml-64 flex flex-col h-screen overflow-hidden bg-background">

  <!-- TopBar (inline for research — has search) -->
  <header class="bg-background flex justify-between items-center h-16 px-margin-desktop w-full z-10 sticky top-0 border-b border-outline-variant/30">
    <div class="flex items-center gap-lg">
      <h2 class="font-headline-md text-headline-md text-primary">Cocoa Agent</h2>
      <nav class="hidden md:flex gap-md ml-lg border-l border-outline-variant pl-lg h-8 items-center">
        <a class="text-on-surface-variant font-ui-medium text-ui-medium hover:text-primary transition-colors" href="#">Planning</a>
        <a class="text-secondary font-semibold font-ui-medium text-ui-medium" href="#">Researching</a>
        <a class="text-on-surface-variant font-ui-medium text-ui-medium hover:text-primary transition-colors" href="#">Verifying</a>
      </nav>
    </div>
    <div class="flex items-center gap-md">
      <div class="relative">
        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">search</span>
        <input
          class="pl-10 pr-4 py-1.5 bg-transparent border-b-2 border-outline-variant focus:border-secondary focus:outline-none font-ui-main text-ui-main text-on-background placeholder:text-outline w-64 transition-colors"
          placeholder="Search insights..."
          type="text"
        />
      </div>
      <button class="text-on-surface-variant hover:text-primary transition-colors p-sm">
        <span class="material-symbols-outlined">notifications</span>
      </button>
      <button class="text-on-surface-variant hover:text-primary transition-colors p-sm">
        <span class="material-symbols-outlined">account_circle</span>
      </button>
    </div>
  </header>

  <!-- Workspace -->
  <main class="flex-1 overflow-hidden flex flex-col p-margin-desktop pt-lg gap-lg">

    <!-- Research Brief -->
    <section class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex justify-between items-start shrink-0 shadow-[0_4px_24px_rgba(106,91,90,0.04)]">
      <div class="max-w-3xl">
        <div class="flex items-center gap-sm mb-sm">
          <span class="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-label-caps text-label-caps flex items-center gap-xs">
            <span class="material-symbols-outlined text-[14px]">psychology</span>
            Synthesizing
          </span>
          <span class="font-status-log text-status-log text-on-surface-variant">Session ID: 492-ARCH-SUS</span>
        </div>
        <h2 class="font-headline-md text-headline-md text-primary mb-xs">Sustainability Trends in Modern Architecture</h2>
        <p class="font-ui-main text-ui-main text-on-surface-variant">
          Investigating the integration of biodegradable materials and passive cooling systems in high-density urban environments, focusing on projects completed after 2020.
        </p>
      </div>
      <div class="flex gap-sm shrink-0 ml-lg">
        <button class="border border-outline-variant text-primary px-4 py-2 rounded-lg font-ui-medium text-ui-medium hover:bg-surface-container-low transition-colors">Edit Scope</button>
        <button class="bg-primary-container text-on-primary px-4 py-2 rounded-lg font-ui-medium text-ui-medium hover:bg-tertiary-container transition-colors">Generate Report</button>
      </div>
    </section>

    <!-- 3-panel layout -->
    <div class="flex-1 flex gap-gutter overflow-hidden min-h-0">

      <!-- Left: Investigation Plan -->
      <aside class="w-72 flex flex-col gap-md shrink-0 overflow-y-auto pr-sm pb-xl">
        <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-xs">Investigation Plan</h3>
        {#each investigationPlan as item}
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-md {item.status === 'pending' ? 'opacity-50' : ''}">
            <div class="flex justify-between items-center mb-sm">
              <span class="font-ui-medium text-ui-medium text-primary">{item.label}</span>
              {#if item.status === 'done'}
                <span class="material-symbols-outlined text-secondary text-[20px]">check_circle</span>
              {:else if item.status === 'running'}
                <span class="material-symbols-outlined text-outline text-[20px] animate-spin" style="animation-duration:2s">sync</span>
              {:else}
                <span class="material-symbols-outlined text-outline text-[20px]">schedule</span>
              {/if}
            </div>
            <div class="w-full bg-surface-variant rounded-full h-1.5 mb-xs">
              <div
                class="h-1.5 rounded-full {item.pct > 0 ? 'bg-secondary' : 'bg-outline-variant'}"
                style="width: {item.pct}%"
              ></div>
            </div>
            <p class="font-status-log text-status-log text-on-surface-variant text-right">
              {item.pct > 0 ? item.pct + '%' : 'Pending'}
            </p>
          </div>
        {/each}
        <div class="mt-lg">
          <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-sm">Overall Confidence</h3>
          <div class="flex items-end gap-sm">
            <span class="font-headline-md text-headline-md text-primary">82%</span>
            <span class="font-status-log text-status-log text-secondary pb-1">+14% this session</span>
          </div>
        </div>
      </aside>

      <!-- Center: Live Synthesis -->
      <section class="flex-1 bg-surface-container-lowest border border-outline-variant rounded-xl shadow-[0_4px_24px_rgba(106,91,90,0.04)] flex flex-col overflow-hidden">
        <div class="p-md border-b border-outline-variant bg-surface/50 sticky top-0 z-10 flex justify-between items-center">
          <h3 class="font-label-caps text-label-caps text-on-surface-variant">Live Synthesis</h3>
          <div class="flex gap-2">
            <button class="p-1 hover:bg-surface-variant rounded text-on-surface-variant transition-colors"><span class="material-symbols-outlined text-[20px]">terminal</span></button>
            <button class="p-1 hover:bg-surface-variant rounded text-on-surface-variant transition-colors"><span class="material-symbols-outlined text-[20px]">open_in_full</span></button>
          </div>
        </div>
        <div class="p-xl overflow-y-auto flex-1 font-body-reading text-body-reading text-on-background max-w-[720px] mx-auto w-full">
          <div class="mb-xl relative">
            <div class="absolute -left-lg top-0 bottom-0 w-[2px] bg-secondary opacity-50"></div>
            <h4 class="font-ui-medium text-ui-medium text-primary mb-sm flex items-center gap-sm">
              <span class="material-symbols-outlined text-secondary text-[18px]">temp_preferences_custom</span>
              Shift Towards Mycelium Composites
            </h4>
            <p class="mb-4">
              Recent data indicates a significant pivot away from traditional carbon-heavy materials toward bio-fabricated alternatives, specifically mycelium-based composites. Unlike early prototypes, contemporary iterations demonstrate compressive strength comparable to conventional concrete while maintaining a negative carbon footprint during production.
            </p>
            <p>
              The synthesis of these materials involves inoculating agricultural waste with fungal spores, which then bind the substrate into a dense matrix. This process, as documented in the recent Milan Expo pavilions, not only sequesters carbon but offers superior insulation properties.
            </p>
          </div>
          <div class="mb-xl">
            <h4 class="font-ui-medium text-ui-medium text-primary mb-sm">Integration of Passive Downdraft Cooling</h4>
            <p class="mb-4">
              Analyzing thermal performance data from twelve high-density residential projects in tropical climates reveals a resurgence in passive downdraft cooling systems. These systems utilize architectural form to induce airflow without mechanical intervention.
            </p>
            <div class="bg-surface-container p-md rounded-lg border border-outline-variant font-status-log text-status-log text-on-surface-variant my-md">
              &gt; query_thermal_efficiency(dataset="tropical_residential_2020_2024")<br/>
              &gt; analyzing 1,240 data points...<br/>
              &gt; result: Average energy reduction of 34.2% compared to standard HVAC baselines.
            </div>
          </div>
        </div>
      </section>

      <!-- Right: Sources & Evidence -->
      <aside class="w-80 flex flex-col gap-md shrink-0 overflow-hidden bg-surface rounded-xl border border-outline-variant p-md">
        <div class="flex justify-between items-center mb-xs pb-sm border-b border-outline-variant">
          <h3 class="font-label-caps text-label-caps text-on-surface-variant">Sources & Evidence</h3>
          <span class="font-status-log text-status-log text-on-surface-variant bg-surface-container-high px-2 py-1 rounded">
            {mockSources.length} Found
          </span>
        </div>
        <div class="overflow-y-auto flex-1 flex flex-col gap-sm pr-sm">
          {#each mockSources as source, i}
            <div class="p-sm rounded-lg hover:bg-surface-container-low transition-colors cursor-pointer
              {i === 0 ? 'border-l-2 border-secondary bg-surface-container-lowest shadow-sm' : 'border border-outline-variant'}
              {source.matchPct < 80 ? 'opacity-70' : ''}">
              <div class="flex justify-between items-start mb-1">
                <span class="font-status-log text-[10px] {i === 0 ? 'text-secondary' : 'text-on-surface-variant'}">
                  Match: {source.matchPct}%
                </span>
                <span class="material-symbols-outlined text-[16px] text-outline">{source.icon}</span>
              </div>
              <h4 class="font-ui-medium text-ui-medium text-primary text-sm mb-1 line-clamp-2">{source.title}</h4>
              <p class="font-ui-main text-[12px] text-on-surface-variant line-clamp-1">{source.publication}</p>
            </div>
          {/each}
        </div>
      </aside>

    </div>
  </main>
</div>
