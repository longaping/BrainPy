# -*- coding: utf-8 -*-

import copy

__all__ = [
  'DictPlus',
]


class DictPlus(dict):
  """Python dictionaries with advanced dot notation access.

  For example:

  >>> d = DictPlus({'a': 10, 'b': 20})
  >>> d.a
  10
  >>> d['a']
  10
  >>> d.c  # this will raise a KeyError
  KeyError: 'c'
  >>> d.c = 30  # but you can assign a value to a non-existing item
  >>> d.c
  30
  """

  def __init__(self, *args, **kwargs):
    object.__setattr__(self, '__parent', kwargs.pop('__parent', None))
    object.__setattr__(self, '__key', kwargs.pop('__key', None))
    for arg in args:
      if not arg:
        continue
      elif isinstance(arg, dict):
        for key, val in arg.items():
          self[key] = self._hook(val)
      elif isinstance(arg, tuple) and (not isinstance(arg[0], tuple)):
        self[arg[0]] = self._hook(arg[1])
      else:
        for key, val in iter(arg):
          self[key] = self._hook(val)

    for key, val in kwargs.items():
      self[key] = self._hook(val)

  def __setattr__(self, name, value):
    if hasattr(self.__class__, name):
      raise AttributeError(f"Attribute '{name}' is read-only in '{type(self)}' object.")
    else:
      self[name] = value

  def __setitem__(self, name, value):
    super(DictPlus, self).__setitem__(name, value)
    try:
      p = object.__getattribute__(self, '__parent')
      key = object.__getattribute__(self, '__key')
    except AttributeError:
      p = None
      key = None
    if p is not None:
      p[key] = self
      object.__delattr__(self, '__parent')
      object.__delattr__(self, '__key')

  def __add__(self, other):
    if not self.keys():
      return other
    else:
      self_type = type(self).__name__
      other_type = type(other).__name__
      msg = "Unsupported operand type(s) for +: '{}' and '{}'"
      raise TypeError(msg.format(self_type, other_type))

  @classmethod
  def _hook(cls, item):
    if isinstance(item, dict):
      return cls(item)
    elif isinstance(item, (list, tuple)):
      return type(item)(cls._hook(elem) for elem in item)
    return item

  def __getattr__(self, item):
    return self.__getitem__(item)

  def __delattr__(self, name):
    del self[name]

  def copy(self):
    return copy.copy(self)

  def deepcopy(self):
    return copy.deepcopy(self)

  def __deepcopy__(self, memo):
    other = self.__class__()
    memo[id(self)] = other
    for key, value in self.items():
      other[copy.deepcopy(key, memo)] = copy.deepcopy(value, memo)
    return other

  def to_dict(self):
    base = {}
    for key, value in self.items():
      if isinstance(value, type(self)):
        base[key] = value.to_dict()
      elif isinstance(value, (list, tuple)):
        base[key] = type(value)(item.to_dict() if isinstance(item, type(self)) else item
                                for item in value)
      else:
        base[key] = value
    return base

  def update(self, *args, **kwargs):
    other = {}
    if args:
      if len(args) > 1:
        raise TypeError()
      other.update(args[0])
    other.update(kwargs)
    for k, v in other.items():
      if (k not in self) or (not isinstance(self[k], dict)) or (not isinstance(v, dict)):
        self[k] = v
      else:
        self[k].update(v)

  def __getnewargs__(self):
    return tuple(self.items())

  def __getstate__(self):
    return self

  def __setstate__(self, state):
    self.update(state)

  def setdefault(self, key, default=None):
    if key in self:
      return self[key]
    else:
      self[key] = default
      return default
