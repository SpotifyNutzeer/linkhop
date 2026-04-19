import { writable } from 'svelte/store';
import type { ServiceInfo } from '$lib/api/types';

export const services = writable<Record<string, ServiceInfo>>({});
