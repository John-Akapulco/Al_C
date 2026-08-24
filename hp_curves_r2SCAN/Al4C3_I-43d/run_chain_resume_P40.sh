#!/bin/sh
# r2SCAN H(P) resume for Al4C3_I-43d: P0-P30 already converged (chain
# 58462 crashed at P40 with "Error EDDDAV: Call to ZHEGV failed" -- a
# numerical instability during SCF, not a bad seed; P40's WAVECAR/CHGCAR
# in this directory were never overwritten by the crashed run, so they
# are still the pristine PBE-seeded restart files). This resumes the
# same-pressure-PBE-seeded, no-inter-point-restart scheme from P40 through
# P100.
#SBATCH --job-name=r2scan_I-43d_resume
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=r2scan_I-43d_resume.log
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
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/r2scan_I-43d_resume.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}

run_step "P40"
run_step "P50"
run_step "P60"
run_step "P70"
run_step "P80"
run_step "P90"
run_step "P100"
echo "$(date '+%F %T') === Al4C3_I-43d: r2SCAN resume P40-P100 done ==="
