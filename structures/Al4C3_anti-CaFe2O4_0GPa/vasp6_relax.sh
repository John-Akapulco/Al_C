#!/bin/sh
#SBATCH --job-name=Al4C3_antiCaFe2O4_0GPa
#SBATCH --nodes=1
#SBATCH --ntasks=40
#SBATCH --cpus-per-task=1
#SBATCH --output=vasp.log
#SBATCH --time=12:00:00

module purge
module load intel
module load impi/2021.13
module load vasp/6.5.0
export OMP_NUM_THREADS=1
ulimit -s unlimited

cp ../Al4C3_anti-CaFe2O4/CONTCAR.relaxed POSCAR
cp ../Al4C3_anti-CaFe2O4/POTCAR POTCAR

cp INCAR.relax INCAR
{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; } 2>> vasp.log
if ! grep -q "General timing" OUTCAR 2>/dev/null; then
    echo "VASP relax step did not finish cleanly -- aborting" >> vasp.log
    exit 1
fi
cp CONTCAR CONTCAR.relaxed
