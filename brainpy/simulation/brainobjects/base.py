# -*- coding: utf-8 -*-

from brainpy import math, errors
from brainpy.base.base import Base
from brainpy.base.collector import Collector
from brainpy.simulation import utils
from brainpy.simulation.monitor import Monitor

ConstantDelay = None

__all__ = [
  'DynamicalSystem',
  'Container',
]

_error_msg = 'Unknown model type: {type}. ' \
             'Currently, BrainPy only supports: \n' \
             '1. function \n' \
             '2. function name (str) \n' \
             '3. tuple/dict of functions \n' \
             '4. tuple of function names \n'


class DynamicalSystem(Base):
  """Base Dynamical System class.

  Any object has step functions will be a dynamical system.
  That is to say, in BrainPy, the essence of the dynamical system
  is the "step functions".

  Parameters
  ----------
  steps : tuple of str, tuple of function, dict of (str, function), optional
      The callable function, or a list of callable functions.
  monitors : None, list, tuple, datastructures.Monitor
      Variables to monitor.
  name : str, optional
      The name of the dynamic system.
  """

  def __init__(self, steps=None, monitors=None, name=None):
    super(DynamicalSystem, self).__init__(name=name)

    # step functions
    if steps is None:
      steps = ('update',)
    self.steps = Collector()
    if isinstance(steps, tuple):
      for step in steps:
        if isinstance(step, str):
          self.steps[step] = getattr(self, step)
        elif callable(step):
          self.steps[step.__name__] = step
        else:
          raise errors.BrainPyError(_error_msg.format(type(steps[0])))
    elif isinstance(steps, dict):
      for key, step in steps.items():
        if callable(step):
          self.steps[key] = step
        else:
          raise errors.BrainPyError(_error_msg.format(type(step)))
    else:
      raise errors.BrainPyError(_error_msg.format(type(steps)))

    # monitors
    if monitors is None:
      self.mon = Monitor(target=self, variables=[])
    elif isinstance(monitors, (list, tuple, dict)):
      self.mon = Monitor(target=self, variables=monitors)
    elif isinstance(monitors, Monitor):
      self.mon = monitors
      self.mon.target = self
    else:
      raise errors.BrainPyError(f'"monitors" only supports list/tuple/dict/ '
                                f'instance of Monitor, not {type(monitors)}.')

    # runner and run function
    self._input_step = None
    self._monitor_step = None

    # batch size
    self.num_batch = None

  def register_constant_delay(self, key, size, delay, dtype=None):
    """Register a constant delay.

    Parameters
    ----------
    key : str
      The delay name.
    size : int, list of int, tuple of int
      The delay data size.
    delay : int, float, ndarray
      The delay time, with the unit same with `brainpy.math.get_dt()`.
    dtype : optional
      The data type.

    Returns
    -------
    delay : ConstantDelay
        An instance of ConstantDelay.
    """
    global ConstantDelay
    if ConstantDelay is None: from brainpy.simulation.brainobjects.delays import ConstantDelay

    if not hasattr(self, 'steps'):
      raise errors.BrainPyError('Please initialize the super class first before '
                                'registering constant_delay. \n\n'
                                'super(YourClassName, self).__init__(**kwargs)')
    if not key.isidentifier(): raise ValueError(f'{key} is not a valid identifier.')
    cdelay = ConstantDelay(size=size,
                           delay=delay,
                           num_batch=getattr(self, 'num_batch', None),
                           name=f'{self.name}_delay_{key}',
                           dtype=dtype)
    self.steps[f'{key}_update'] = cdelay.update
    return cdelay

  def update(self, _t, _dt, **kwargs):
    """The function to specify the updating rule.

    Parameters
    ----------
    _t : float
      The current time.
    _dt : float
      The time step.
    """
    raise NotImplementedError('Must implement "update" function by user self.')

  def run(self, duration, dt=None, report=0., inputs=(), extra_func=None):
    """The running function.

    Parameters
    ----------
    inputs : list, tuple
      The inputs for this instance of DynamicalSystem. It should the format
      of `[(target, value, [type, operation])]`, where `target` is the
      input target, `value` is the input value, `type` is the input type
      (such as "fix" or "iter"), `operation` is the operation for inputs
      (such as "+", "-", "*", "/", "=").

      - ``target``: should be a string. Can be specified by the *absolute access* or *relative access*.
      - ``value``: should be a scalar, vector, matrix, iterable function or objects.
      - ``type``: should be a string. "fix" means the input `value` is a constant. "iter" means the
        input `value` can be changed over time.
      - ``operation``: should be a string, support `+`, `-`, `*`, `/`, `=`.
      - Also, if you want to specify multiple inputs, just give multiple ``(target, value, [type, operation])``,
        for example ``[(target1, value1), (target2, value2)]``.

    duration : float, int, tuple, list
      The running duration.

    report : float
      The percent of progress to report. [0, 1]. If zero, the model
      will not output report progress.

    dt : float, optional
      The numerical integration step size.

    extra_func : function, callable
      The extra function to run during each time step.

    Returns
    -------
    running_time : float
      The total running time.
    """

    if dt is None:
      dt = math.get_dt()
    assert isinstance(dt, (int, float))

    # 2. Build the inputs.
    #    All the inputs are wrapped into a single function.
    self._input_step = utils.build_input_func(
      utils.check_and_format_inputs(host=self, inputs=inputs), show_code=False)

    # 3. Build the monitors.
    #    All the monitors are wrapped in a single function.
    if self._monitor_step is None:
      self._monitor_step = utils.build_monitor_func(
        utils.check_and_format_monitors(host=self), show_code=False)
    else:
      for node in self.nodes().unique().values():
        for key in node.mon.item_contents.keys():
          node.mon.item_contents[key] = []  # reshape the monitor items

    # 4. times
    start, end = utils.check_duration(duration)
    times = math.arange(start, end, dt)

    # 5. run the model
    # ----
    # 5.1 iteratively run the step function.
    # 5.2 report the running progress.
    # 5.3 return the overall running time.

    def step_run(_t, _dt, **kwargs):
      self._input_step(_t=_t, _dt=_dt)
      for step in self.steps.values():
        step(_t=_t, _dt=_dt, **kwargs)
      self._monitor_step(_t=_t, _dt=_dt)

    running_time = utils.run_model(run_func=step_run,
                                   times=times,
                                   report=report,
                                   dt=dt,
                                   extra_func=extra_func)

    # 6. monitor
    # --
    # 6.1 add 'ts' variable to every monitor
    # 6.2 wrap the monitor iterm with the 'list' type into the 'ndarray' type
    for node in self.nodes().unique().values():
      if node.mon.num_item > 0:
        node.mon.ts = times
        for key, val in list(node.mon.item_contents.items()):
          val = math.asarray(node.mon.item_contents[key])
          node.mon.item_contents[key] = val

    return running_time

  def find_fixed_points(self):
    pass

  def evaluate_stability(self):
    pass

  def continuation(self, method='euler_newton'):
    pass


class Container(DynamicalSystem):
  """Container object which is designed to add other instances of DynamicalSystem.

  Parameters
  ----------
  steps : tuple of function, tuple of str, dict of (str, function), optional
      The step functions.
  monitors : tuple, list, Monitor, optional
      The monitor object.
  name : str, optional
      The object name.
  show_code : bool
      Whether show the formatted code.
  ds_dict : dict of (str, )
      The instance of DynamicalSystem with the format of "key=dynamic_system".
  """

  def __init__(self, *ds_tuple, steps=None, monitors=None, name=None, **ds_dict):
    # children dynamical systems
    self.child_ds = dict()
    for ds in ds_tuple:
      if not isinstance(ds, DynamicalSystem):
        raise errors.BrainPyError(f'{self.__class__.__name__} receives instances of '
                                  f'DynamicalSystem, however, we got {type(ds)}.')
      if ds.name in self.child_ds:
        raise ValueError(f'{ds.name} has been paired with {ds}. Please change a unique name.')
      self.child_ds[ds.name] = ds
    for key, ds in ds_dict.items():
      if not isinstance(ds, DynamicalSystem):
        raise errors.BrainPyError(f'{self.__class__.__name__} receives instances of '
                                  f'DynamicalSystem, however, we got {type(ds)}.')
      if key in self.child_ds:
        raise ValueError(f'{key} has been paired with {ds}. Please change a unique name.')
      self.child_ds[key] = ds
    # step functions in children dynamical systems
    self.child_steps = dict()
    for ds_key, ds in self.child_ds.items():
      for step_key, step in ds.steps.items():
        self.child_steps[f'{ds_key}_{step_key}'] = step

    # integrative step function
    if steps is None:
      steps = ('update',)
    super(Container, self).__init__(steps=steps, monitors=monitors, name=name)

  def update(self, _t, _dt):
    """Step function of a network.

    In this update function, the step functions in children systems are
    iteratively called.
    """
    for step in self.child_steps.values():
      step(_t, _dt)

  def nodes(self, method='absolute', _paths=None):
    if _paths is None:
      _paths = set()
    gather = self._nodes_in_container(self.child_ds, method=method, _paths=_paths)
    gather.update(super(Container, self).nodes(method=method, _paths=_paths))
    return gather

  def __getattr__(self, item):
    children_ds = super(Container, self).__getattribute__('child_ds')
    if item in children_ds:
      return children_ds[item]
    else:
      return super(Container, self).__getattribute__(item)
