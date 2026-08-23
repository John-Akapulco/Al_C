#!/bin/bash
# Submit the Al4C3 r2SCAN H(P) scan: one SLURM job per phase, each
# reserving a single node for its entire 11-point series (0 to 100 GPa,
# each point independently seeded from the converged PBE WAVECAR/CHGCAR
# at the same pressure -- see hp_curves/gen_hp_runs_r2scan.py).
#
# NOT executed automatically -- run manually after review:
#   cd hp_curves_r2SCAN && ./submit_chain.sh | tee submitted_ids.txt

set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PHASES=(I-43d Pnma-III Pnma Pnma-VII R-3m Pbam anti-CaFe2O4)

for phase in "${PHASES[@]}"; do
    pdir="$BASE/Al4C3_${phase}"
    jid=$(cd "$pdir" && sbatch run_chain.sh | awk '{print $4}')
    echo -e "${phase}\t${jid}"
done
