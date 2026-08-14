import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import type { UserProfile } from '$lib/api/types';

export const userProfile = writable<UserProfile>({
  username: ''
});

export async function loadUserProfile(): Promise<UserProfile> {
  try {
    const profile = await api.getProfile();
    if (profile && profile.username && profile.username.trim() && profile.username.toLowerCase() !== 'user') {
      userProfile.set({ username: profile.username.trim() });
      return profile;
    }
  } catch (err) {
    console.warn('Failed to load user profile state:', err);
  }
  const fallback: UserProfile = { username: '' };
  userProfile.set(fallback);
  return fallback;
}
