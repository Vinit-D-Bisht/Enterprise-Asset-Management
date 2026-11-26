export type SetupDetails = { full_name: string; email: string; password: string; confirm_password: string };

export function validateSetupDetails(details: SetupDetails): string {
  if (details.full_name.trim().length < 2) return "Enter your full name (at least 2 characters).";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(details.email.trim())) return "Enter a valid email address.";
  if (details.password.length < 12 || details.password.length > 200) return "Password must be between 12 and 200 characters.";
  if (details.password !== details.confirm_password) return "Password confirmation does not match.";
  return "";
}
