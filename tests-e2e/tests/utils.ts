// Drupal sometimes renders absolute URLs using the host-facing hostname
// (localhost:18080 here), which is unreachable from inside the test-runner
// container. Extracting just the path keeps navigation going through baseURL.
export function pathOf(href: string): string {
  const url = new URL(href, 'http://placeholder');
  return url.pathname + url.search;
}
