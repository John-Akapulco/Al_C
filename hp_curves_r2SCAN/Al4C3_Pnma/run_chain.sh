#!/bin/sh
# r2SCAN H(P) scan for Al4C3_Pnma: 11 pressure points, each already
# seeded from its own converged PBE WAVECAR/CHGCAR (no inter-point
# restart needed here, unlike the PBE chain) -- run sequentially on one
# node to keep the same one-job-per-phase submission footprint.
#SBATCH --job-name=r2scan_Pnma
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=r2scan_Pnma.log
#SBATCH --time=96:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

BASE="$SLURM_SUBMIT_DIR"

run_step() {
    local dir="$1"
    echo "$(date '+%F %T') === starting $dir ==="
    cd "$BASE/$dir" || exit 1
    cp INCAR.relax INCAR
    { time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; } 2>> vasp.log
    if ! grep -q "General timing" OUTCAR 2>/dev/null; then
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/r2scan_Pnma.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}

run_step "P0"
run_step "P10"
run_step "P20"
run_step "P30"
run_step "P40"
run_step "P50"
run_step "P60"
run_step "P70"
run_step "P80"
run_step "P90"
run_step "P100"
echo "$(date '+%F %T') === Al4C3_Pnma: r2SCAN 0-100 GPa series done ==="
