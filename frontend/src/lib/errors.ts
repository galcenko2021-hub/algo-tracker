export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Что-то пошло не так";
}
