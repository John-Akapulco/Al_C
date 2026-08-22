#!/bin/sh
#SBATCH --job-name=Al4C3_Pnma-VII_50GPa
#SBATCH --nodes=1
#SBATCH --ntasks=40
#SBATCH --exclude=node01,node02,node03,node04,node05,node06,node07,node08
#SBATCH --threads-per-core=1
#SBATCH --cpus-per-task=1
#SBATCH --output=vasp.log
#SBATCH --time=12:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

cp INCAR.relax INCAR
{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 --threads-per-core=1 vasp_std ; } 2>> vasp.log
if ! grep -q "General timing" OUTCAR 2>/dev/null; then
    echo "VASP relax step did not finish cleanly -- aborting" >> vasp.log
    exit 1
fi
cp CONTCAR CONTCAR.relaxed
