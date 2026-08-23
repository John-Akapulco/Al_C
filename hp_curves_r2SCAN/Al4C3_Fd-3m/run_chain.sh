#!/bin/sh
#SBATCH --job-name=r2scan_Fd-3m
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=r2scan_Fd-3m.log
#SBATCH --time=96:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

BASE="$SLURM_SUBMIT_DIR"

run_step() {
    local dir="$1" prev="$2"
    echo "$(date '+%F %T') === starting $dir (prev=${prev:-none}) ==="
    cd "$BASE/$dir" || exit 1
    if [ -n "$prev" ]; then
        cp "../$prev/CONTCAR" POSCAR
        cp "../$prev/WAVECAR" WAVECAR
        cp "../$prev/CHGCAR" CHGCAR
    fi
    cp INCAR.relax INCAR
    { time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; } 2>> vasp.log
    if ! grep -q "General timing" OUTCAR 2>/dev/null; then
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/r2scan_Fd-3m.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}

run_step "P0" ""
run_step "P10" "P0"
run_step "P20" "P10"
run_step "P30" "P20"
run_step "P40" "P30"
run_step "P50" "P40"
run_step "P60" "P50"
run_step "P70" "P60"
run_step "P80" "P70"
run_step "P90" "P80"
run_step "P100" "P90"
echo "$(date '+%F %T') === Al4C3_Fd-3m: r2SCAN 0-100 GPa series done ==="
