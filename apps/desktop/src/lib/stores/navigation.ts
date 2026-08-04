import { writable } from 'svelte/store';

export type Route =
  | 'home'
  | 'projects'
  | 'research'
  | 'tasks'
  | 'automations'
  | 'settings';

export const currentRoute = writable<Route>('home');

export function navigate(route: Route): void {
  currentRoute.set(route);
}
