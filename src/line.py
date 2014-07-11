"""line.py: Contains line class."""
# pylint: disable=E1101,R0903
__author__ = "Durmus U. Karatay"
__copyright__ = "Copyright 2014, Ginger Lab"
__maintainer__ = "Durmus U. Karatay"
__email__ = "ukaratay@uw.edu"
__status__ = "Development"

import numpy as np
import pixel


class Line(object):
    """

    This is container class for a line. See documentation of pixel for details.

    Parameters
    ----------
    signal_array : array, [n_points, n_signals]
        2D real-valued signal array, corresponds to a line.

    n_pixels : int
        Number of pixels in a line.

    params : dict
        Includes parameters for processing. Here is a list of parameters:

        trigger = float (in seconds)
        total_time = float (in seconds)
        sampling_rate = int (in Hz)
        drive_freq = float (in Hz)

        roi = float (in seconds)
        window = string (see documentation of pixel.apply_window)
        bandpass_filter = int (0: no filtering, 1: FIR filter, 2: IIR filter)
        filter_bandwidth = float (in Hz)

    Attributes
    ----------
    `signal_array` : array, shape = [n_points, n_signals]
        Array that contains signals from a line.

    `tfp` : array, shape = [n_pixels]
        Time-to-First-Peak, in seconds.

    `shift` : array, shape = [n_pixels]
        Frequency shift from steady-state to first-peak, in Hz.

    """

    def __init__(self, signal_array, n_pixels, params):

        # Pass inputs to the object.
        self.signal_array = signal_array
        self.n_pixels = n_pixels
        self.params = params

        # Initialize tFP and shift arrays.
        self.tfp = np.empty(self.n_pixels)
        self.shift = np.empty(self.n_pixels)

        return

    def get_tfp(self):
        """Runs the analysis for a line and outputs tFPs and shifts."""

        # Split the signal array into pixels.
        pixel_signals = np.split(self.signal_array, self.n_pixels, axis=1)

        # Iterate over pixels and return tFP and shift arrays.
        for i, pix in enumerate(pixel_signals):

            p = pixel.Pixel(pix, self.params)
            self.tfp[i], self.shift[i] = p.get_tfp()

        return (self.tfp, self.shift)
