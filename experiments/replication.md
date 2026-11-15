# Replication R1 of the EXP-008 protocol

Written 15 November 2026, before the run.

**Purpose.** Repeat the frozen [protocol](protocol.md) once, live, from this repository's code. The first run (`results/2026-11-14-specialists-live-v2/`) was made from the private research repository, which also held earlier generations of the graph. Those have been removed here and the modules renamed. The prompts, schemas, cases, checks and call budget are unchanged. This run shows whether the published code reproduces the published result, and gives a second observation of each configuration.

**What is the same.** The four cases, the four configurations, one pass each (16 jobs, at most 56 model calls, cap 60), the model and reasoning effort from the environment, the primary endpoint, and the rule that reference answers and final utility values never reach a model.

**What differs.** Module and file names; the manifest label (`EXP-008-R1`); the date.

**How it will be reported.** Beside the first run, never pooled with it. The two runs share the same four authored cases, so they are repeated observations of those cases, not eight independent cases. Whatever the counts are, they are reported as they come out, including a configuration doing worse than before. No further run is made in response to the result.
