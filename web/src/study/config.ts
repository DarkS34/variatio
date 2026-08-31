/**
 * WHAT PART OF THE STUDY THIS BUILD SHOWS.
 *
 * The blind comparison has two halves. One is somebody asking for a comparison of their
 * own and judging it — that is the whole loop, and it works alone. The other is CROSS
 * EVALUATION: an administrator generates a batch in some workspace, hands each set to the
 * evaluators competent to judge it, and the panel then computes agreement between people
 * who judged the same three exercises.
 *
 * The second half is switched off here (2026-08-31, explicit user request). It is what
 * turns the screen from «pide una comparación y dila» into an operator's queue — a
 * destination somebody else fills, with a pending count and a triage backlog — and this
 * branch is a path a teacher walks alone.
 *
 * NOTHING IS DELETED FOR IT. The queue tab, the assignment panel, the set copies and the
 * agreement arithmetic are all still there and still tested; what changes is that no
 * screen offers them. Turning this back to `true` is the whole of putting cross evaluation
 * back, which is the only reason it is a flag and not a diff.
 *
 * The server is untouched either way: hiding a route in the browser is not a permission,
 * and `POST /api/admin/evaluations/sets/{id}/assign` still answers to an administrator.
 */
export const CROSS_EVALUATION = false;
