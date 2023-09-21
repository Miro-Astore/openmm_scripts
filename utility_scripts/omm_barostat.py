"""
Generated by CHARMM-GUI (http://www.charmm-gui.org)

omm_barostat.py

This module is for pressure coupling methods in OpenMM.

Correspondance: jul316@lehigh.edu or wonpil@lehigh.edu
Last update: March 29, 2017
"""

from simtk.unit import *
from openmm import *
from openmm.app import *

def barostat(system, inputs):

    if inputs.p_type == 'isotropic':
        barostat = MonteCarloBarostat( inputs.p_ref*bar, inputs.temp*kelvin )
    if inputs.p_type == 'membrane':
        inputs.p_tens = inputs.p_tens*10.0
        barostat = MonteCarloMembraneBarostat( inputs.p_ref*bar, inputs.p_tens*bar*nanometers, inputs.temp*kelvin, inputs.p_XYMode, inputs.p_ZMode, inputs.p_freq )
    if inputs.p_type == 'anisotropic':
        barostat = MonteCarloAnisotropicBarostat( inputs.p_ref*bar, inputs.temp*kelvin, inputs.p_scale[0], inputs.p_scale[1], inputs.p_scale[2], inputs.p_freq )

    system.addForce(barostat)

    return system
