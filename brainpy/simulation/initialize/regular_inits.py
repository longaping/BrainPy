# -*- coding: utf-8 -*-

from .base import Initializer
from brainpy import math

__all__ = [
  'ZeroInit',
  'OneInit',
  'Identity',
]


class ZeroInit(Initializer):
  """Zero initializer.

  Initialize the weights with zeros.
  """

  def __call__(self, shape):
    return math.zeros(shape, dtype=self.dtype)


class OneInit(Initializer):
  """One initializer.

  Initialize the weights with the given values.

  Parameters
  ----------
  value : float, int, math.ndarray
    The value to specify.
  """

  def __init__(self, value=1., dtype=None):
    super(OneInit, self).__init__(dtype=dtype)
    self.value = value

  def __call__(self, shape):
    return math.ones(shape, dtype=self.dtype) * self.value


class Identity(Initializer):
  """Returns the identity matrix.

  This initializer was proposed in (Le, et al., 2015) [1]_.

  Parameters
  ----------
  value : float
    The optional scaling factor.

  Returns
  -------
  shape: tuple of int
    The weight shape/size.

  References
  ----------
  .. [1] Le, Quoc V., Navdeep Jaitly, and Geoffrey E. Hinton. "A simple way to
         initialize recurrent networks of rectified linear units." arXiv preprint
         arXiv:1504.00941 (2015).
  """

  def __init__(self, value=1., dtype=None):
    super(Identity, self).__init__(dtype=dtype)
    self.value = value

  def __call__(self, shape):
    if isinstance(shape, int):
      shape = (shape, )
    elif isinstance(shape, (tuple, list)):
      if len(shape) > 2:
        raise ValueError(f'Only support initialize 2D weights for {self.__class__.__name__}.')
    else:
      raise ValueError(f'Only support shape of int, or tuple/list of int '
                       f'in {self.__class__.__name__}, but we got {shape}.')
    return math.eye(*shape, dtype=self.dtype) * self.value
