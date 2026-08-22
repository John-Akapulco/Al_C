#!/bin/bash
# Submit the Al4C3 H(P) scan: one SLURM job per phase, each reserving a
# single node for its entire 11-point series (0 to 100 GPa), running the
# points sequentially inside that one allocation (see run_chain.sh).
#
# NOT executed automatically -- run manually after review:
#   cd hp_curves && ./submit_chain.sh | tee submitted_ids.txt

set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PHASES=(I-43d Pnma-III Pnma Pnma-VII R-3m Pbam anti-CaFe2O4)

for phase in "${PHASES[@]}"; do
    pdir="$BASE/Al4C3_${phase}"
    jid=$(cd "$pdir" && sbatch run_chain.sh | awk '{print $4}')
    echo -e "${phase}\t${jid}"
done
