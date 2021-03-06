"""simulate.py: Contains Cantilever class."""
# pylint: disable=E1101,R0902,C0103
__author__ = "Durmus U. Karatay"
__copyright__ = "Copyright 2020, Ginger Lab"
__maintainer__ = "Rajiv Giridharaogpal"
__email__ = "rgiri@uw.edu"
__status__ = "Production"

import numpy as np
from scipy.integrate import odeint

import ffta

# Set constant 2 * pi.
PI2 = 2 * float(np.pi)


class Cantilever:
	"""Damped Driven Harmonic Oscillator Simulator for AFM Cantilevers.
	Simulates a DDHO with given parameters.
	
	This class contains the functions needed to simulate. To create a class that
	simulates a subset, it needs to overload the following functions:
		force(self, t)
		omega(self, t)
		dZdt(self, t) if the given ODE form will not work

	Parameters
	----------
	can_params : dict
		Parameters for cantilever properties. The dictionary contains:

		amp_invols = float (in m/V)
		def_invols = float (in m/V)
		soft_amp = float (in V)
		drive_freq = float (in Hz)
		res_freq = float (in Hz)
		k = float (in N/m)
		q_factor = float

	force_params : dict
		Parameters for forces. The dictionary contains:

		es_force = float (in N)
		delta_freq = float (in Hz)
		tau = float (in seconds)
		v_dc = float (in Volts)
		v_ac = float (in Volts)
		v_cpd = float (in Volts)
		dCdz = float (in F/m)

	sim_params : dict
		Parameters for simulation. The dictionary contains:

		trigger = float (in seconds)
		total_time = float (in seconds)
		sampling_rate = int (in Hz)


	Attributes
	----------
	amp : float
		Amplitude of the cantilever in meters.
	beta : float
		Damping factor of the cantilever in rad/s.
	delta : float
		Initial phase of the cantilever in radians.
	delta_freq : float
		Frequency shift of the cantilever under excitation.
	mass : float
		Mass of the cantilever in kilograms.
	Z : ndarray
		ODE integration result, sampled at sampling_rate. Default integration
		is at 100 MHz.
	t_Z : ndarray
		Time axis based on the provided total time and sampling rate
	f_Z : ndarray
		Frequency axis based on the provided sampling rate

	Method
	------
	simulate(trigger_phase=180)
		Simulates the cantilever motion with excitation happening
		at the given phase.

	See Also
	--------
	pixel: Pixel processing for FF-trEFM data.

	Examples
	--------
	>>> from ffta.simulation import cantilever, load
	>>>
	>>> params_file = '../examples/sim_params.cfg'
	>>> params = load.simulation_configuration(params_file)
	>>>
	>>> c = cantilever.Cantilever(*params)
	>>> Z, infodict = c.simulate()
	>>> c.analyze()
	>>> c.analyze(roi=0.004) # can change the parameters as desired

	"""

	def __init__(self, can_params, force_params, sim_params):

		# Initialize cantilever parameters and calculate some others.
		for key, value in can_params.items():
			setattr(self, key, value)

		self.w0 = PI2 * self.res_freq  # Radial resonance frequency.
		self.wd = PI2 * self.drive_freq  # Radial drive frequency.

		if not np.allclose(self.w0, self.wd):
			print('Resonance and Drive not equal. Make sure simulation is long enough!')

		self.beta = self.w0 / (2 * self.q_factor)  # Damping factor.
		self.mass = self.k / (self.w0 ** 2)  # Mass of the cantilever in kg.
		self.amp = self.soft_amp * self.amp_invols  # Amplitude in meters.

		# Calculate reduced driving force and phase in equilibrium.
		np.seterr(divide='ignore')  # suprress divide-by-0 warning in arctan
		self.f0 = self.amp * np.sqrt((self.w0 ** 2 - self.wd ** 2) ** 2 +
									 4 * self.beta ** 2 * self.wd ** 2)
		self.delta = np.abs(np.arctan(np.divide(2 * self.wd * self.beta,
												self.w0 ** 2 - self.wd ** 2)))

		# Initialize force parameters and calculate some others.
		for key, value in force_params.items():
			setattr(self, key, value)

		self.delta_w = PI2 * self.delta_freq  # Frequency shift in radians.
		self.fe = self.es_force / self.mass  # Reduced electrostatic force.

		# Initialize simulation parameters.
		for key, value in sim_params.items():
			setattr(self, key, value)

		# Calculate time axis for simulated tip motion without extra cycles
		num_pts = int(self.total_time * self.sampling_rate)
		self.t_Z = np.linspace(0, self.total_time, num=num_pts)

		# Calculate frequency axis for simulated tip_motion without extra cycles.
		self.freq_Z = np.linspace(0, int(self.sampling_rate / 2), num=int(num_pts / 2 + 1))

		# Create a Pixel class-compatible params file
		self.fit_params = {}
		self.parameters = force_params
		self.parameters.update(**sim_params)
		self.can_params = can_params
		self.create_parameters(self.parameters, self.can_params)

		return

	def set_conditions(self, trigger_phase=180):
		"""
		Sets initial conditions and other simulation parameters.

		Parameters
		----------
		trigger_phase: float, optional
		   Trigger phase is in degrees and wrt cosine. Default value is 180.

		"""

		self.trigger_phase = np.mod(np.pi * trigger_phase / 180, PI2)
		self.n_points = int(self.total_time * self.sampling_rate)

		# Add extra cycles to the simulation to find correct phase at trigger.
		cycle_points = int(2 * self.sampling_rate / self.res_freq)
		self.n_points_sim = cycle_points + self.n_points

		# Create time vector and find the trigger wrt phase.
		self.t = np.arange(self.n_points_sim) / self.sampling_rate

		# Current phase at trigger.
		current_phase = np.mod(self.wd * self.trigger - self.delta, PI2)
		phase_diff = np.mod(self.trigger_phase - current_phase, PI2)

		self.t0 = self.trigger + phase_diff / self.wd  # modified trigger point

		# Set the initial conditions at t=0.
		z0 = self.amp * np.sin(-self.delta)
		v0 = self.amp * self.wd * np.cos(-self.delta)

		self.Z0 = np.array([z0, v0])

		return

	def force(self, t, t0=0, tau=0):
		"""
		Force on the cantilever at a given time. 

		Parameters
		----------
		t : float
			Time in seconds.

		Returns
		-------
		f : float
			Force on the cantilever at a given time, in N/kg.

		"""

		driving_force = self.f0 * np.sin(self.wd * t)

		return driving_force

	def omega(self, t, t0=0, tau=0):
		"""
		Resonance frequency behavior

		Parameters
		----------
		t : float
			Time in seconds.

		Returns
		-------
		w : float
			Resonance frequency of the cantilever at a given time, in rad/s.

		"""

		return self.w0

	def dZ_dt(self, Z, t=0):
		"""
		Takes the derivative of the given Z with respect to time.

		Parameters
		----------
		Z : (2, ) array_like
			Z[0] is the cantilever position, and Z[1] is the cantilever
			velocity.
		t : float
			Time.

		Returns
		-------
		Zdot : (2, ) array_like
			Zdot[0] is the cantilever velocity, and Zdot[1] is the cantilever
			acceleration.

		"""

		t0 = self.t0
		tau = self.tau

		v = Z[1]
		vdot = (self.force(t, t0, tau) -
				self.omega(t, t0, tau) * Z[1] / self.q_factor -
				self.omega(t, t0, tau) ** 2 * Z[0])

		return np.array([v, vdot])

	def simulate(self, trigger_phase=180, Z0=None):
		"""
		Simulates the cantilever motion.

		Parameters
		----------
		trigger_phase: float, optional
		   Trigger phase is in degrees and wrt cosine. Default value is 180.
		Z0 : list, optional
			Z0 = [z0, v0], the initial position and velocity
			If not specified, is calculated from the analytical solution to DDHO
			(using "set_conditions")
		Returns
		-------
		Z : (n_points, 1) array_like
			Cantilever position in Volts.
		infodict : dict
			Information about the ODE solver.

		"""

		if Z0:

			if not isinstance(Z0, (np.ndarray, list)):
				raise TypeError('Must be 2-size array or list')
			if len(Z0) != 2:
				raise ValueError('Must specify exactly [z0, v0]')

			self.n_points = int(self.total_time * self.sampling_rate)
			self.t = np.arange(self.n_points) / self.sampling_rate
			self.t0 = self.trigger
			self.Z0 = Z0

		else:
			self.set_conditions(trigger_phase)

		Z, infodict = odeint(self.dZ_dt, self.Z0, self.t, full_output=True)

		t0_idx = int(self.t0 * self.sampling_rate)
		tidx = int(self.trigger * self.sampling_rate)
		Z_cut = Z[(t0_idx - tidx):(t0_idx + self.n_points - tidx), 0]

		self.infodict = infodict
		self.Z = Z_cut
		return self.Z, self.infodict

	def downsample(self, target_rate=1e7):
		'''
		Downsamples the cantilever output. Used primarily to match experiments
		or for lower computational load
		
		This will overwrite the existing output with the downsampled verison
		
		target_rate : int
			The sampling rate for the signal to be converted to. 1e7 = 10 MHz
		'''

		if target_rate > self.sampling_rate:
			raise ValueError('Target should be less than the initial sampling rate')
		step = int(self.sampling_rate / target_rate)
		n_points = int(self.total_time * target_rate)

		self.Z = self.Z[0::step].reshape(n_points, 1) / self.def_invols

		return

	def create_parameters(self, params={}, can_params={}, fit_params={}):
		'''
		Creates a Pixel class-compatible parameters and cantilever parameters Dict
		
		Parameters
		----------
		params : dict, optional
			Contains analysis parameters for the Pixel cass
		
		can_params : dict, optional
			Contains cantilever parameters for the Pixel class. These data are
			optional for the analysis.
		
		fit_params : dict, optional
			Contains various parameters for fitting and analysis. See Pixel class.
		'''

		# default seeding of parameters
		_parameters = {'bandpass_filter': 1.0,
					   'drive_freq': 277261,
					   'filter_bandwidth': 10000.0,
					   'n_taps': 799,
					   'roi': 0.0003,
					   'sampling_rate': 1e7,
					   'total_time': 0.002,
					   'trigger': 0.0005,
					   'window': 'blackman',
					   'wavelet_analysis': 0,
                       'fft_params': {}}

		_can_params = {'amp_invols': 5.52e-08,
					   'def_invols': 5.06e-08,
					   'k': 26.2,
					   'q_factor': 432}

		_fit_params = {'filter_amplitude': True,
					   'method': 'hilbert',
					   'fit': True,
					   'fit_form': 'product'
                       }

		for key, val in _parameters.items():
			if key not in params:
				if hasattr(self, key):
					params[key] = self.__dict__[key]
				else:
					params[key] = val

		for key, val in _can_params.items():
			if key not in can_params:
				if hasattr(self, key):
					can_params[key] = self.__dict__[key]
				else:
					can_params[key] = val

		for key, val in _fit_params.items():
			if key not in fit_params:
				if hasattr(self, key):
					fit_params[key] = self.__dict__[key]
				else:
					fit_params[key] = val

		# then write to the Class
		self.parameters.update(**params)
		self.can_params.update(**can_params)
		self.fit_params.update(**fit_params)

		return

	def analyze(self, plot=True, **kwargs):
		'''
		Converts output to a Pixel class and analyzes
		
		Parameters
		----------
		plot : bool, optional
			If True, calls Pixel.plot() to display the results
		

		Returns
		-------
		pix : Pixel object

		'''
		param_keys = ['bandpass_filter', 'drive_freq', 'filter_bandwidth', 'n_taps',
					  'roi', 'sampling_rate', 'total_time', 'trigger', 'window', 'wavelet_analysis',
                      'fft_params']

		can_param_keys = ['amp_invols', 'def_invols', 'k', 'q_factor']

		fit_param_keys = ['filter_amplitude', 'method', 'fit', 'fit_form']

		params = {}
		can_params = {}
		fit_params = {}

		for k, v in kwargs.items():
			if k in param_keys:
				params[k] = v
			elif k in can_param_keys:
				can_params[k] = v
			elif k in fit_param_keys:
				fit_params[k] = v

		self.create_parameters(params, can_params, fit_params)

		pix = ffta.pixel.Pixel(self.Z, self.parameters, self.can_params, **self.fit_params)

		pix.analyze()

		if plot:
			pix.plot()

		return pix
