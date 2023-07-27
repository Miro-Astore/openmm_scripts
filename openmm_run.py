"""
Generated by CHARMM-GUI (http://www.charmm-gui.org)

openmm_run.py

This program is OpenMM running scripts written in python.

Correspondance: jul316@lehigh.edu or wonpil@lehigh.edu
Last update: June 18, 2021
"""

from __future__ import print_function
import argparse
import sys
import os

import pdb
import rlcompleter

#pdb.Pdb.complete=rlcompleter.Completer(locals()).complete

from omm_readinputs import *
from omm_readparams import *
from omm_vfswitch import *
from omm_barostat import *
from omm_restraints import *
from omm_rewrap import *

from simtk.unit import *
from openmm import *
from openmm.app import *
#from openmmtools import integrators as tools_integrators

parser = argparse.ArgumentParser()
parser.add_argument('--platform', nargs=1, help='OpenMM platform (default: CUDA or OpenCL)')
parser.add_argument('-i', dest='inpfile', help='Input parameter file', required=True)
parser.add_argument('-p', dest='topfile', help='Input topology file', required=True)
parser.add_argument('-c', dest='crdfile', help='Input coordinate file')
parser.add_argument('-ipdb', dest='input_pdbfile', help='Input coordinate pdb file')
parser.add_argument('-t', dest='toppar', help='Input CHARMM-GUI toppar stream file (optional)')
parser.add_argument('-b', dest='sysinfo', help='Input CHARMM-GUI sysinfo stream file (optional)')
parser.add_argument('-ff', dest='fftype', help='Input force field type (default: CHARMM)', default='CHARMM')
parser.add_argument('-icrst', metavar='RSTFILE', dest='icrst', help='Input CHARMM RST file (optional)')
parser.add_argument('-irst', metavar='RSTFILE', dest='irst', help='Input restart file (optional)')
parser.add_argument('-ichk', metavar='CHKFILE', dest='ichk', help='Input checkpoint file (optional)')
parser.add_argument('-opdb', metavar='PDBFILE', dest='opdb', help='Output PDB file (optional)')
parser.add_argument('-orst', metavar='RSTFILE', dest='orst', help='Output restart file (optional)')
parser.add_argument('-ochk', metavar='CHKFILE', dest='ochk', help='Output checkpoint file (optional)')
parser.add_argument('-odcd', metavar='DCDFILE', dest='odcd', help='Output trajectory file (optional)')
parser.add_argument('-rewrap', dest='rewrap', help='Re-wrap the coordinates in a molecular basis (optional)', action='store_true', default=False)
parser.add_argument('--restart-timer', dest='restart_timer', help='Choose whether to restart the timer from zero or not.', action='store_true', default=False)
args = parser.parse_args()

# Load parameters
print("Loading parameters")
inputs = read_inputs(args.inpfile)


print('making top')
top = read_top(args.topfile, args.fftype.upper())
print('done')

crd = read_crd(args.crdfile, args.fftype.upper())

if args.input_pdbfile is not None : 
    crd = PDBFile(args.input_pdbfile, args.fftype.upper())
    params = read_params(args.toppar)
    top = read_box(top, args.sysinfo) if args.sysinfo else gen_box(top, crd)

#if args.fftype.upper() == 'CHARMM':

# Build system
print("building system")
nboptions = dict(nonbondedMethod=inputs.coulomb,
                 nonbondedCutoff=inputs.r_off*nanometers,
                 constraints=inputs.cons,
                 ewaldErrorTolerance=inputs.ewald_Tol,
                 hydrogenMass = 4 * amu)
if inputs.vdw == 'Switch': nboptions['switchDistance'] = inputs.r_on*nanometers
if inputs.vdw == 'LJPME':  nboptions['nonbondedMethod'] = LJPME
if inputs.implicitSolvent:
    nboptions['implicitSolvent'] = inputs.implicitSolvent
    nboptions['implicitSolventSaltConc'] = inputs.implicit_salt*(moles/liter)
    nboptions['temperature'] = inputs.temp*kelvin
    nboptions['soluteDielectric'] = inputs.solut_diele
    nboptions['solventDielectric'] = inputs.solve_diele
    nboptions['gbsaModel'] = inputs.gbsamodel

if   args.fftype.upper() == 'CHARMM': system = top.createSystem(params, **nboptions)
elif args.fftype.upper() == 'AMBER':  
    system = top.createSystem(**nboptions)

if inputs.vdw == 'Force-switch': system = vfswitch(system, top, inputs)
if inputs.lj_lrc == 'yes':
    for force in system.getForces():
        if isinstance(force, NonbondedForce): force.setUseDispersionCorrection(True)
        if isinstance(force, CustomNonbondedForce) and force.getNumTabulatedFunctions() != 1:
            force.setUseLongRangeCorrection(True)
if inputs.e14scale != 1.0:
    for force in system.getForces():
        if isinstance(force, NonbondedForce): nonbonded = force; break
    for i in range(nonbonded.getNumExceptions()):
        atom1, atom2, chg, sig, eps = nonbonded.getExceptionParameters(i)
        nonbonded.setExceptionParameters(i, atom1, atom2, chg*inputs.e14scale, sig, eps)

if inputs.pcouple == 'yes':      system = barostat(system, inputs)
if inputs.rest == 'yes':         system = restraints(system, crd, inputs)
integrator = LangevinMiddleIntegrator(inputs.temp*kelvin, inputs.fric_coeff/picosecond, inputs.dt*picoseconds)
#integrator = GeodesicBAOABIntegrator(temperature = inputs.temp*kelvin, collision_rate = inputs.fric_coeff/picosecond, timestep =  inputs.dt*picoseconds)
print('done')

# Set platform
DEFAULT_PLATFORMS = 'CUDA', 'OpenCL', 'CPU'
enabled_platforms = [Platform.getPlatform(i).getName() for i in range(Platform.getNumPlatforms())]
if args.platform:
    if not args.platform[0] in enabled_platforms:
        print("Unable to find OpenMM platform '{}'; exiting".format(args.platform[0]), file=sys.stderr)
        sys.exit(1)

    platform = Platform.getPlatformByName(args.platform[0])
else:
    for platform in DEFAULT_PLATFORMS:
        if platform in enabled_platforms:
            platform = Platform.getPlatformByName(platform)
            break
    if isinstance(platform, str):
        print("Unable to find any OpenMM platform; exiting".format(args.platform[0]), file=sys.stderr)
        sys.exit(1)

print("Using platform:", platform.getName())
prop = dict(CudaPrecision='single') if platform.getName() == 'CUDA' else dict()

# Build simulation context
print('building system')
simulation = Simulation(top.topology, system, integrator, platform, prop)

if args.icrst:
    charmm_rst = read_charmm_rst(args.icrst)
    simulation.context.setPositions(charmm_rst.positions)
    simulation.context.setVelocities(charmm_rst.velocities)
    simulation.context.setPeriodicBoxVectors(charmm_rst.box[0], charmm_rst.box[1], charmm_rst.box[2])
else:
    simulation.context.setPositions(crd.positions)

if args.irst:
    with open(args.irst, 'r') as f:
        simulation.context.setState(XmlSerializer.deserialize(f.read()))
if args.ichk:
    with open(args.ichk, 'rb') as f:
        simulation.context.loadCheckpoint(f.read())
#if args.restart_timer == True:
#    positions = simulation.context.getState(getPositions=True)
#    print(type(positions.Positions))
#    velocities = simulation.context.getState(getVelocities=True)
#    box_vectors = simulation.context.getSystem().getDefaultPeriodicBoxVectors
#    del integrator
#    integrator = LangevinIntegrator(inputs.temp*kelvin, inputs.fric_coeff/picosecond, inputs.dt*picoseconds)
#    integrator = integrator 
#    simulation2 = Simulation (top.topology, system, integrator, platform, prop)
#    simulation.context.setPositions(positions)
#    simulation.context.setVelocities(velocities)
#    simulation.context.setPeriodicBoxVectors(box_vectors)

if args.restart_timer == True:
    simulation.context.setTime (0 * unit.picoseconds)



# Re-wrap
if args.rewrap:
    simulation = rewrap(simulation)

# Calculate initial system energy
print("\nInitial system energy")
print(simulation.context.getState(getEnergy=True).getPotentialEnergy())

# Energy minimization
if inputs.mini_nstep > 0:
    print("\nEnergy minimization: %s steps" % inputs.mini_nstep)
    simulation.minimizeEnergy(tolerance=inputs.mini_Tol*kilojoule/mole, maxIterations=inputs.mini_nstep)
    print(simulation.context.getState(getEnergy=True).getPotentialEnergy())

# Generate initial velocities
if inputs.gen_vel == 'yes':
    print("\nGenerate initial velocities")
    if inputs.gen_seed:
        simulation.context.setVelocitiesToTemperature(inputs.gen_temp, inputs.gen_seed)
    else:
        simulation.context.setVelocitiesToTemperature(inputs.gen_temp)

# Production
if inputs.nstep > 0:
    print("\nMD run: %s steps" % inputs.nstep)
    if inputs.nstdcd > 0:
        if not args.odcd: args.odcd = 'output.dcd'
        simulation.reporters.append(DCDReporter(args.odcd, inputs.nstdcd))
    simulation.reporters.append(
        StateDataReporter(sys.stdout, inputs.nstout, step=True, time=True, potentialEnergy=True, temperature=True, progress=True,
                          remainingTime=True, speed=True, totalSteps=inputs.nstep, separator='\t')
    )
    # Simulated annealing?
    if inputs.annealing == 'yes':
        interval = inputs.interval
        temp = inputs.temp_init
        for i in range(inputs.nstep):
            integrator.setTemperature(temp*kelvin)
            simulation.step(1)
            temp += interval
    else:
        simulation.step(inputs.nstep)

# Write restart file
if not (args.orst or args.ochk): args.orst = 'output.rst'
if args.orst:
    state = simulation.context.getState( getPositions=True, getVelocities=True )
    with open(args.orst, 'w') as f:
        f.write(XmlSerializer.serialize(state))
if args.ochk:
    with open(args.ochk, 'wb') as f:
        f.write(simulation.context.createCheckpoint())
if args.opdb:
    crd = simulation.context.getState(getPositions=True).getPositions()
    PDBFile.writeFile(top.topology, crd, open(args.opdb, 'w'))

