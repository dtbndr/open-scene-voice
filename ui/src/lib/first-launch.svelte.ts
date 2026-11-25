// In-memory only (U15): the Projects page sets it when there is no key and no project; the Keys screen reads it.
export const firstLaunch = $state({ value: false });

// Once per page load: the Projects page runs the first-launch check at most once, and the layout marks it done
// when the page was opened somewhere else than `/`.
export const launchCheck = { done: false };
