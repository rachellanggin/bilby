from ..core.utils import logger

try:
    from astropy import cosmology as cosmo, units
    DEFAULT_COSMOLOGY = cosmo.Planck15
    COSMOLOGY = [DEFAULT_COSMOLOGY, DEFAULT_COSMOLOGY.name]
except ImportError:
    logger.warning("You do not have astropy installed currently. You will"
                   " not be able to use some of the prebuilt functions.")
    DEFAULT_COSMOLOGY = None
    COSMOLOGY = [None, str(None)]

from . import (calibration, conversion, detector, likelihood, prior, series,
               source, utils, waveform_generator)

from .waveform_generator import WaveformGenerator
from .likelihood import GravitationalWaveTransient


def set_cosmology(cosmology=None):
    """
    Get an instance of a astropy.cosmology.FLRW subclass.

    To avoid repeatedly instantiating the same class, test if it is the same
    as the last used cosmology.

    Parameters
    ----------
    cosmology: astropy.cosmology.FLRW, str, dict
        Description of cosmology, one of:
            None - Use DEFAULT_COSMOLOGY
            Instance of astropy.cosmology.FLRW subclass
            String with name of known Astropy cosmology, e.g., "Planck13"
            Dictionary with arguments required to instantiate the cosmology
            class.

    Returns
    -------
    cosmo: astropy.cosmology.FLRW
        Cosmology instance
    """
    if str(cosmology) == str(COSMOLOGY[1]):
        pass
    else:
        if cosmology is None:
            cosmology = DEFAULT_COSMOLOGY
        elif isinstance(cosmology, cosmo.FLRW):
            cosmology = cosmology
        elif isinstance(cosmology, str):
            cosmology = cosmo.__dict__[cosmology]
        elif isinstance(cosmology, dict):
            if 'Ode0' in cosmology.keys():
                if 'w0' in cosmology.keys():
                    cosmology = cosmo.wCDM(**cosmology)
                else:
                    cosmology = cosmo.LambdaCDM(**cosmology)
            else:
                cosmology = cosmo.FlatLambdaCDM(**cosmology)
        COSMOLOGY[0] = cosmology
        COSMOLOGY[1] = cosmology.name
