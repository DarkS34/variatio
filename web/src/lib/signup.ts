/**
 * What the registration form checks as the person types, mirrored from the server.
 *
 * Two mirrors, and the server stays the authority for both: `usernameFromName` is
 * `server/auth/queries.username_from_name` without the number a namesake adds (only the
 * server knows who has a name), and `passwordChecks` is `server/auth/passwords.policy_error`
 * split into the three things a person can act on. A change to either rule there changes it
 * here in the same commit; `signup.test.ts` holds the cases both sides must agree on.
 */

/** The words of a name a username leaves out (`queries._NAME_PARTICLES`). */
const NAME_PARTICLES = new Set(["de", "del", "la", "las", "los", "y", "e", "da", "das", "do", "dos", "di", "van", "von"]);

/** Room left under the 64 characters for the number that tells two namesakes apart. */
const USERNAME_BASE_MAX = 58;

/**
 * The username the server will make from this name, before any number: the first name, a dot
 * and the next word, accents folded and particles and initials left out. Empty for no name.
 */
export function usernameFromName(name: string): string {
  if (!name.trim()) return "";
  const plain = name.toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");
  const words = plain.split(/[^a-z0-9]+/).filter(Boolean);
  const kept = words.filter((word) => word.length > 1 && !NAME_PARTICLES.has(word));
  const base = (kept.length > 0 ? kept : words)
    .slice(0, 2)
    .join(".")
    .slice(0, USERNAME_BASE_MAX)
    .replace(/^[._-]+|[._-]+$/g, "");
  if (!base) return "usuario";
  return base.length < 3 ? `${base}1` : base;
}

/** `passwords.MIN_LENGTH`. */
export const PASSWORD_MIN = 12;

const PASSWORD_MAX = 256;

/** `passwords._COMMON`: the short list a length rule alone still lets through. */
const COMMON = new Set([
  "contraseña", // i18n-exempt: un dato que se compara, nunca se pinta
  "contrasena",
  "password",
  "passw0rd",
  "administrador",
  "administrator",
  "qwertyuiop",
  "1234567890",
  "12345678901",
  "123456789012",
  "iloveyou",
  "welcome",
  "letmein",
  "abc123",
  "generador",
  "variantes",
]);

const KEYBOARD_ROWS = ["abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm"];

/** What a password still lacks, as three things a person can act on. */
export type PasswordChecks = {
  /** At least `PASSWORD_MIN` characters, and no more than the server keeps. */
  length: boolean;
  /** Neither the name nor the username inside it. */
  personal: boolean;
  /** Not a common word, a keyboard run or one character repeated. */
  obvious: boolean;
  /** How many characters it has, as the server counts them. */
  count: number;
};

/** Check a password against the server's policy for an account with this name and username. */
export function passwordChecks(password: string, who: { name: string; username: string }): PasswordChecks {
  const normal = password.normalize("NFKC");
  const count = [...normal].length;
  const lowered = normal.toLowerCase();
  const stripped = lowered.normalize("NFD").replace(/\p{M}/gu, "");
  const local = who.username.split("@")[0].toLowerCase();
  const personal = [local, who.name.toLowerCase()].every(
    (part) => part.length < 4 || !lowered.includes(part),
  );
  const repeated = count > 0 && /^(.)\1*$/su.test(normal);
  const sequence =
    count >= PASSWORD_MIN &&
    KEYBOARD_ROWS.some((row) => {
      const doubled = row + row;
      return doubled.includes(lowered) || [...doubled].reverse().join("").includes(lowered);
    });
  const common = COMMON.has(lowered) || COMMON.has(stripped);
  return {
    length: count >= PASSWORD_MIN && count <= PASSWORD_MAX,
    personal,
    obvious: count > 0 && !common && !repeated && !sequence,
    count,
  };
}

/** Whether every check passes: the form sends nothing the server would refuse for its policy. */
export function passwordAccepted(checks: PasswordChecks): boolean {
  return checks.length && checks.personal && checks.obvious;
}
