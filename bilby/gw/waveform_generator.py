import numpy as np
from ..core import utils
from ..gw.series import CoupledTimeAndFrequencySeries


class WaveformGenerator(object):

    def __init__(self, duration=None, sampling_frequency=None, start_time=0, frequency_domain_source_model=None,
                 time_domain_source_model=None, parameters=None,
                 parameter_conversion=None,
                 waveform_arguments=None):
        """ A waveform generator

    Parameters
    ----------
    sampling_frequency: float, optional
        The sampling frequency
    duration: float, optional
        Time duration of data
    start_time: float, optional
        Starting time of the time array
    frequency_domain_source_model: func, optional
        A python function taking some arguments and returning the frequency
        domain strain. Note the first argument must be the frequencies at
        which to compute the strain
    time_domain_source_model: func, optional
        A python function taking some arguments and returning the time
        domain strain. Note the first argument must be the times at
        which to compute the strain
    parameters: dict, optional
        Initial values for the parameters
    parameter_conversion: func, optional
        Function to convert from sampled parameters to parameters of the
        waveform generator. Default value is the identity, i.e. it leaves
        the parameters unaffected.
    waveform_arguments: dict, optional
        A dictionary of fixed keyword arguments to pass to either
        `frequency_domain_source_model` or `time_domain_source_model`.

        Note: the arguments of frequency_domain_source_model (except the first,
        which is the frequencies at which to compute the strain) will be added to
        the WaveformGenerator object and initialised to `None`.

        """
        self._times_and_frequencies = CoupledTimeAndFrequencySeries(duration=duration,
                                                                    sampling_frequency=sampling_frequency,
                                                                    start_time=start_time)
        self.duration = duration
        self.sampling_frequency = sampling_frequency
        self.start_time = start_time
        self.frequency_domain_source_model = frequency_domain_source_model
        self.time_domain_source_model = time_domain_source_model
        self.source_parameter_keys = self.__parameters_from_source_model()
        if parameter_conversion is None:
            self.parameter_conversion = lambda params: (params, [])
        else:
            self.parameter_conversion = parameter_conversion
        if waveform_arguments is not None:
            self.waveform_arguments = waveform_arguments
        else:
            self.waveform_arguments = dict()
        if isinstance(parameters, dict):
            self.parameters = parameters

    def __repr__(self):
        if self.frequency_domain_source_model is not None:
            fdsm_name = self.frequency_domain_source_model.__name__
        else:
            fdsm_name = None
        if self.time_domain_source_model is not None:
            tdsm_name = self.time_domain_source_model.__name__
        else:
            tdsm_name = None
        if self.parameter_conversion.__name__ == '<lambda>':
            param_conv_name = None
        else:
            param_conv_name = self.parameter_conversion.__name__

        return self.__class__.__name__ + '(duration={}, sampling_frequency={}, start_time={}, ' \
                                         'frequency_domain_source_model={}, time_domain_source_model={}, ' \
                                         'parameter_conversion={}, ' \
                                         'waveform_arguments={})'\
            .format(self.duration, self.sampling_frequency, self.start_time, fdsm_name, tdsm_name,
                    param_conv_name, self.waveform_arguments)

    def frequency_domain_strain(self, parameters=None):
        """ Wrapper to source_model.

        Converts self.parameters with self.parameter_conversion before handing it off to the source model.
        Automatically refers to the time_domain_source model via NFFT if no frequency_domain_source_model is given.

        Parameters
        ----------
        parameters: dict, optional
            Parameters to evaluate the waveform for, this overwrites
            `self.parameters`.
            If not provided will fall back to `self.parameters`.

        Returns
        -------
        array_like: The frequency domain strain for the given set of parameters

        Raises
        -------
        RuntimeError: If no source model is given

        """
        return self._calculate_strain(model=self.frequency_domain_source_model,
                                      model_data_points=self.frequency_array,
                                      parameters=parameters,
                                      transformation_function=utils.nfft,
                                      transformed_model=self.time_domain_source_model,
                                      transformed_model_data_points=self.time_array)

    def time_domain_strain(self, parameters=None):
        """ Wrapper to source_model.

        Converts self.parameters with self.parameter_conversion before handing it off to the source model.
        Automatically refers to the frequency_domain_source model via INFFT if no frequency_domain_source_model is
        given.

        Parameters
        ----------
        parameters: dict, optional
            Parameters to evaluate the waveform for, this overwrites
            `self.parameters`.
            If not provided will fall back to `self.parameters`.

        Returns
        -------
        array_like: The time domain strain for the given set of parameters

        Raises
        -------
        RuntimeError: If no source model is given

        """
        return self._calculate_strain(model=self.time_domain_source_model,
                                      model_data_points=self.time_array,
                                      parameters=parameters,
                                      transformation_function=utils.infft,
                                      transformed_model=self.frequency_domain_source_model,
                                      transformed_model_data_points=self.frequency_array)

    def _calculate_strain(self, model, model_data_points, transformation_function, transformed_model,
                          transformed_model_data_points, parameters):
        if parameters is not None:
            self.parameters = parameters
        if model is not None:
            model_strain = self._strain_from_model(model_data_points, model)
        elif transformed_model is not None:
            model_strain = self._strain_from_transformed_model(transformed_model_data_points, transformed_model,
                                                               transformation_function)
        else:
            raise RuntimeError("No source model given")
        return model_strain

    def _strain_from_model(self, model_data_points, model):
        return model(model_data_points, **self.parameters)

    def _strain_from_transformed_model(self, transformed_model_data_points, transformed_model, transformation_function):
        transformed_model_strain = self._strain_from_model(transformed_model_data_points, transformed_model)

        if isinstance(transformed_model_strain, np.ndarray):
            return transformation_function(transformed_model_strain, self.sampling_frequency)

        model_strain = dict()
        for key in transformed_model_strain:
            if transformation_function == utils.nfft:
                model_strain[key], self.frequency_array = \
                    transformation_function(transformed_model_strain[key], self.sampling_frequency)
            else:
                model_strain[key] = transformation_function(transformed_model_strain[key], self.sampling_frequency)
        return model_strain

    @property
    def parameters(self):
        """ The dictionary of parameters for source model.

        Returns
        -------
        dict: The dictionary of parameter key-value pairs

        """
        return self.__parameters

    @parameters.setter
    def parameters(self, parameters):
        """
        Set parameters, this applies the conversion function and then removes
        any parameters which aren't required by the source function.

        (set.symmetric_difference is the opposite of set.intersection)

        Parameters
        ----------
        parameters: dict
            Input parameter dictionary, this is copied, passed to the conversion
            function and has self.waveform_arguments added to it.
        """
        if not isinstance(parameters, dict):
            raise TypeError('"parameters" must be a dictionary.')
        new_parameters = parameters.copy()
        new_parameters, _ = self.parameter_conversion(new_parameters)
        for key in self.source_parameter_keys.symmetric_difference(
                new_parameters):
            new_parameters.pop(key)
        self.__parameters = new_parameters
        self.__parameters.update(self.waveform_arguments)

    def __parameters_from_source_model(self):
        """
        Infer the named arguments of the source model.

        Returns
        -------
        set: The names of the arguments of the source model.
        """
        if self.frequency_domain_source_model is not None:
            model = self.frequency_domain_source_model
        elif self.time_domain_source_model is not None:
            model = self.time_domain_source_model
        else:
            raise AttributeError('Either time or frequency domain source '
                                 'model must be provided.')
        return set(utils.infer_parameters_from_function(model))

    @property
    def frequency_array(self):
        """ Frequency array for the waveforms. Automatically updates if sampling_frequency or duration are updated.

        Returns
        -------
        array_like: The frequency array
        """
        return self._times_and_frequencies.frequency_array

    @frequency_array.setter
    def frequency_array(self, frequency_array):
        self._times_and_frequencies.frequency_array = frequency_array

    @property
    def time_array(self):
        """ Time array for the waveforms. Automatically updates if sampling_frequency or duration are updated.

        Returns
        -------
        array_like: The time array
        """
        return self._times_and_frequencies.time_array

    @time_array.setter
    def time_array(self, time_array):
        self._times_and_frequencies.time_array = time_array

    @property
    def duration(self):
        """ Allows one to set the time duration and automatically updates the frequency and time array.

        Returns
        -------
        float: The time duration.

        """
        return self._times_and_frequencies.duration

    @duration.setter
    def duration(self, duration):
        self._times_and_frequencies.duration = duration

    @property
    def sampling_frequency(self):
        """ Allows one to set the sampling frequency and automatically updates the frequency and time array.

        Returns
        -------
        float: The sampling frequency.

        """
        return self._times_and_frequencies.sampling_frequency

    @sampling_frequency.setter
    def sampling_frequency(self, sampling_frequency):
        self._times_and_frequencies.sampling_frequency = sampling_frequency

    @property
    def start_time(self):
        return self._times_and_frequencies.start_time

    @start_time.setter
    def start_time(self, start_time):
        self._times_and_frequencies.start_time = start_time
