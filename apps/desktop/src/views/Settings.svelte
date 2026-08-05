<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';

  let backendConnected = false;

  onMount(async () => {
    backendConnected = await api.checkHealth();
  });
</script>

<main class="ml-64 pt-24 px-margin-desktop pb-xxl">
  <div class="max-w-[640px]">
    <div class="mb-xl">
      <h2 class="font-label-caps text-label-caps text-on-surface-variant mb-xs">CONFIGURATION</h2>
      <h1 class="font-display-lg text-display-lg text-primary">Settings</h1>
    </div>

    <!-- LLM Provider -->
    <section class="mb-xl">
      <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md tracking-wider">LLM PROVIDER</h3>
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg space-y-md">
        <div>
          <label class="font-ui-medium text-ui-medium text-primary block mb-xs">Provider</label>
          <select class="w-full bg-surface border border-outline-variant rounded-lg px-md py-sm font-ui-main text-ui-main text-on-surface focus:border-secondary focus:outline-none transition-colors">
            <option>Groq</option>
            <option>OpenAI</option>
            <option>Gemini</option>
            <option>Ollama (Local)</option>
          </select>
        </div>
        <div>
          <label class="font-ui-medium text-ui-medium text-primary block mb-xs">API Key</label>
          <input
            type="password"
            placeholder="sk-••••••••••••••••"
            class="w-full bg-surface border border-outline-variant rounded-lg px-md py-sm font-ui-main text-ui-main text-on-surface placeholder:text-on-surface-variant/40 focus:border-secondary focus:outline-none transition-colors"
          />
          <p class="font-ui-main text-[13px] text-on-surface-variant mt-xs opacity-70">
            Keys are stored locally and never sent to any third party.
          </p>
        </div>
        <div>
          <label class="font-ui-medium text-ui-medium text-primary block mb-xs">Model</label>
          <input
            type="text"
            placeholder="e.g. llama-3.3-70b-versatile"
            class="w-full bg-surface border border-outline-variant rounded-lg px-md py-sm font-ui-main text-ui-main text-on-surface placeholder:text-on-surface-variant/40 focus:border-secondary focus:outline-none transition-colors"
          />
        </div>
        <div class="pt-sm border-t border-outline-variant flex justify-end">
          <button class="bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary-container px-lg py-sm rounded-full font-ui-medium text-ui-medium transition-colors shadow-sm">
            Save Settings
          </button>
        </div>
      </div>
    </section>

    <!-- Agent -->
    <section class="mb-xl">
      <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md tracking-wider">AGENT</h3>
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg space-y-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-ui-medium text-ui-medium text-primary">Backend URL</p>
            <p class="font-ui-main text-[13px] text-on-surface-variant">Python FastAPI service</p>
          </div>
          <input
            type="text"
            value="http://localhost:8000"
            class="bg-surface border border-outline-variant rounded-lg px-md py-sm font-status-log text-status-log text-on-surface focus:border-secondary focus:outline-none transition-colors w-56"
          />
        </div>
        <div class="flex items-center justify-between pt-sm border-t border-outline-variant">
          <div>
            <p class="font-ui-medium text-ui-medium text-primary">Agent Status</p>
            <p class="font-ui-main text-[13px] text-on-surface-variant">Backend connection</p>
          </div>
          {#if backendConnected}
            <div class="flex items-center gap-sm bg-secondary-container/30 border border-secondary-fixed-dim/30 px-md py-[6px] rounded-full">
              <span class="w-2 h-2 rounded-full bg-secondary-fixed-dim"></span>
              <span class="font-label-caps text-label-caps text-on-secondary-container">Connected</span>
            </div>
          {:else}
            <div class="flex items-center gap-sm bg-error/10 border border-error/20 px-md py-[6px] rounded-full">
              <span class="w-2 h-2 rounded-full bg-error"></span>
              <span class="font-label-caps text-label-caps text-error">Not connected</span>
            </div>
          {/if}
        </div>
      </div>
    </section>

    <!-- About -->
    <section>
      <h3 class="font-label-caps text-label-caps text-on-surface-variant mb-md tracking-wider">ABOUT</h3>
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
        <div class="flex items-center gap-md">
          <div class="w-12 h-12 rounded-full bg-primary-container flex items-center justify-center">
            <span class="material-symbols-outlined text-on-primary-container fill text-[24px]">psychology</span>
          </div>
          <div>
            <p class="font-ui-medium text-ui-medium text-primary">Cocoa Personal Agent</p>
            <p class="font-ui-main text-[13px] text-on-surface-variant">Version 0.1.0 · Phase 1</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</main>
