/** Normalize unknown failures at UI boundaries without assuming an Error shape. */
export function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message) return cause.message;
  if (typeof cause === 'object' && cause !== null && 'message' in cause && typeof cause.message === 'string' && cause.message) return cause.message;
  return fallback;
}
