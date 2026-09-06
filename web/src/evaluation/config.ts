/**
 * What part of the study this build shows.
 *
 * The blind comparison has two halves: somebody asking for a comparison of their own and
 * judging it, which works alone, and CROSS EVALUATION — an administrator stocking a
 * workspace, handing each set to the evaluators competent to judge it, and the panel
 * computing agreement between people who judged the same three exercises.
 *
 * The second is switched off: it turns the screen into an operator's queue somebody else
 * fills, and this build is a path a teacher walks alone.
 *
 * NOTHING is deleted for it — the queue tab, the assignment panel, the set copies and the
 * agreement arithmetic are all still there and still tested, and no screen offers them.
 * Turning this back to `true` is the whole of putting cross evaluation back, which is the
 * only reason it is a flag and not a diff. The server is untouched either way.
 */
export const CROSS_EVALUATION = false;
