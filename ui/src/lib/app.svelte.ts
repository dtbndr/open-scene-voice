// The one job store and the one connection watcher of the page; the root layout starts the watcher.
import { api } from './api/client';
import { Connection } from './connection/connection.svelte';
import { JobStore, type EventSourceLike } from './jobs/store.svelte';

export const jobs = new JobStore({
  fetchJob: () => api.currentJob(),
  createSource: (url) => new EventSource(url) as unknown as EventSourceLike
});

export const connection = new Connection({
  poll: () => jobs.refresh(),
  streamOpen: () => jobs.streamOpen
});
