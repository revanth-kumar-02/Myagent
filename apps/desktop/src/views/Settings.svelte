<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';

  let backendConnected = false;

  onMount(async () => {
    backendConnected = await api.checkHealth();
  });
</script>

<main class="ml-56 pt-12 px-6 pb-6 min-h-[calc(100vh-48px)] bg-background flex flex-col flex-1">
  <div class="max-w-2xl w-full pt-2">
    <div class="mb-4 border-b border-outline-variant/40 pb-3">
      <h2 class="font-label-caps text-[10px] text-on-surface-variant/80 mb-0.5 tracking-wider">CONFIGURATION</h2>
      <h1 class="font-headline-md text-[18px] text-primary font-semibold">Settings</h1>
    </div>

    <!-- LLM Provider -->
    <section class="mb-5">
      <h3 class="font-label-caps text-[11px] text-on-surface-variant/80 mb-2 tracking-wider font-semibold">LLM PROVIDER</h3>
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 space-y-3 shadow-sm">
        <div>
          <label for="settings-provider-select" class="font-ui-medium text-[12px] text-primary block mb-1">Provider</label>
          <select id="settings-provider-select" class="w-full bg-surface border border-outline-variant/50 rounded-md px-3 py-1 font-ui-main text-[12px] text-on-surface focus:border-secondary focus:outline-none transition-colors h-8">
            <option>Groq</option>
            <option>OpenAI</option>
            <option>Gemini</option>
            <option>Ollama (Local)</option>
          </select>
        </div>
        <div>
          <label for="settings-api-key-input" class="font-ui-medium text-[12px] text-primary block mb-1">API Key</label>
          <input
            id="settings-api-key-input"
            type="password"
            placeholder="sk-••••••••••••••••"
            class="w-full bg-surface border border-outline-variant/50 rounded-md px-3 py-1 font-ui-main text-[12px] text-on-surface placeholder:text-on-surface-variant/40 focus:border-secondary focus:outline-none transition-colors h-8"
          />
          <p class="font-ui-main text-[11px] text-on-surface-variant/70 mt-1">
            Keys are stored locally and never sent to any third party.
          </p>
        </div>
        <div>
          <label for="settings-model-input" class="font-ui-medium text-[12px] text-primary block mb-1">Model</label>
          <input
            id="settings-model-input"
            type="text"
            placeholder="e.g. llama-3.3-70b-versatile"
            class="w-full bg-surface border border-outline-variant/50 rounded-md px-3 py-1 font-ui-main text-[12px] text-on-surface placeholder:text-on-surface-variant/40 focus:border-secondary focus:outline-none transition-colors h-8"
          />
        </div>
        <div class="pt-2 border-t border-outline-variant/40 flex justify-end">
          <button class="bg-primary text-on-primary hover:bg-primary-container px-3.5 py-1 rounded-md font-ui-medium text-[12px] transition-colors shadow-sm h-8">
            Save Settings
          </button>
        </div>
      </div>
    </section>

    <!-- Agent -->
    <section class="mb-5">
      <h3 class="font-label-caps text-[11px] text-on-surface-variant/80 mb-2 tracking-wider font-semibold">AGENT</h3>
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-4 space-y-3 shadow-sm">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-ui-medium text-[12px] text-primary">Backend URL</p>
            <p class="font-ui-main text-[11px] text-on-surface-variant/70">Python FastAPI service</p>
          </div>
          <input
            type="text"
            value="http://localhost:8000"
            class="bg-surface border border-outline-variant/50 rounded-md px-3 py-1 font-status-log text-[11px] text-on-surface focus:border-secondary focus:outline-none transition-colors w-52 h-8"
          />
        </div>
        <div class="flex items-center justify-between pt-2 border-t border-outline-variant/40">
          <div>
            <p class="font-ui-medium text-[12px] text-primary">Agent Status</p>
            <p class="font-ui-main text-[11px] text-on-surface-variant/70">Backend connection</p>
          </div>
          {#if backendConnected}
            <div class="flex items-center gap-1.5 bg-secondary-container/30 border border-secondary-fixed-dim/30 px-2.5 py-0.5 rounded-full">
              <span class="w-1.5 h-1.5 rounded-full bg-secondary-fixed-dim"></span>
              <span class="font-label-caps text-[10px] text-on-secondary-container">Connected</span>
            </div>
          {:else}
            <div class="flex items-center gap-1.5 bg-error/10 border border-error/20 px-2.5 py-0.5 rounded-full">
              <span class="w-1.5 h-1.5 rounded-full bg-error"></span>
              <span class="font-label-caps text-[10px] text-error">Not connected</span>
            </div>
          {/if}
        </div>
      </div>
    </section>

    <!-- About -->
    <section>
      <h3 class="font-label-caps text-[11px] text-on-surface-variant/80 mb-2 tracking-wider font-semibold">ABOUT</h3>
      <div class="bg-surface-container-lowest border border-outline-variant/60 rounded-md p-3.5 shadow-sm">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-primary-container flex items-center justify-center shrink-0">
            <span class="material-symbols-outlined text-on-primary-container fill text-[20px]">psychology</span>
          </div>
          <div>
            <p class="font-ui-medium text-[13px] text-primary font-medium">Cocoa Personal Agent</p>
            <p class="font-ui-main text-[11px] text-on-surface-variant/80">Version 0.1.0 · Autonomous Workspace Agent</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</main>
