/** The subjects of an account: the selector's rows and a subject's summary. */

import type { Role } from "./auth";
import type { ArtifactName, ArtifactStatus } from "./pipeline";

export interface WorkspaceRow {
  slug: string;
  name: string;
  role: Role | null;
  active: boolean;
  /** Listed only because the account administers the installation, not by membership. */
  as_admin: boolean;
  /** This account's own exercises there. Only the listing sends it, and an older API not even that. */
  exercises?: number;
  /** Who is in it, counted — only where this account teaches, and only from an API that counts. */
  people?: SubjectPeople;
  /** A teacher paused this account's access: listed, and nothing opens. Absent from an older API. */
  disabled?: boolean;
}

/** A subject's people, counted: active students, paused members, active teachers. */
export interface SubjectPeople {
  students: number;
  disabled: number;
  teachers: number;
}

export interface WorkspaceListing {
  workspaces: WorkspaceRow[];
  active: string | null;
  can_create: boolean;
}

export interface WorkspaceSummary {
  slug: string;
  name: string;
  role: Role;
  stages: { artifact: ArtifactName; label: string; status: ArtifactStatus }[];
  ready: boolean;
  generations: number;
}
