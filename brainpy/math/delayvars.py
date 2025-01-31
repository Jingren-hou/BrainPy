# -*- coding: utf-8 -*-

from typing import Union, Callable, Tuple

import jax.numpy as jnp
from jax import vmap
from jax.lax import cond

from brainpy import check
from brainpy.base.base import Base
from brainpy.errors import UnsupportedError
from brainpy.math import numpy_ops as bm
from brainpy.math.jaxarray import ndarray, Variable, JaxArray
from brainpy.math.setting import get_dt
from brainpy.tools.checking import check_float, check_integer
from brainpy.tools.errors import check_error_in_jit

__all__ = [
  'AbstractDelay',
  'TimeDelay', 'LengthDelay',
  'NeuTimeDelay', 'NeuLenDelay',
]


class AbstractDelay(Base):
  def update(self, *args, **kwargs):
    raise NotImplementedError


_FUNC_BEFORE = 'function'
_DATA_BEFORE = 'data'
_INTERP_LINEAR = 'linear_interp'
_INTERP_ROUND = 'round'


class TimeDelay(AbstractDelay):
  """Delay variable which has a fixed delay time length.

  For example, we create a delay variable which has a maximum delay length of 1 ms

  >>> import brainpy.math as bm
  >>> delay = bm.TimeDelay(bm.zeros(3), delay_len=1., dt=0.1)
  >>> delay(-0.5)
  [-0. -0. -0.]

  This function supports multiple dimensions of the tensor. For example,

  1. the one-dimensional delay data

  >>> delay = bm.TimeDelay(bm.zeros(3), delay_len=1., dt=0.1, before_t0=lambda t: t)
  >>> delay(-0.2)
  [-0.2 -0.2 -0.2]

  2. the two-dimensional delay data

  >>> delay = bm.TimeDelay(bm.zeros((3, 2)), delay_len=1., dt=0.1, before_t0=lambda t: t)
  >>> delay(-0.6)
  [[-0.6 -0.6]
   [-0.6 -0.6]
   [-0.6 -0.6]]

  3. the three-dimensional delay data

  >>> delay = bm.TimeDelay(bm.zeros((3, 2, 1)), delay_len=1., dt=0.1, before_t0=lambda t: t)
  >>> delay(-0.8)
  [[[-0.8]
    [-0.8]]
   [[-0.8]
    [-0.8]]
   [[-0.8]
    [-0.8]]]

  Parameters
  ----------
  delay_target: JaxArray, ndarray, Variable
    The initial delay data.
  t0: float, int
    The zero time.
  delay_len: float, int
    The maximum delay length.
  dt: float, int
    The time precesion.
  before_t0: callable, bm.ndarray, jnp.ndarray, float, int
    The delay data before ::math`t_0`.
    - when `before_t0` is a function, it should receive a time argument `t`
    - when `before_to` is a tensor, it should be a tensor with shape
      of :math:`(num\_delay, ...)`, where the longest delay data is aranged in
      the first index.
  name: str
    The delay instance name.
  interp_method: str
    The way to deal with the delay at the time which is not integer times of the time step.
    For exameple, if the time step ``dt=0.1``, the time delay length ``delay\_len=1.``,
    when users require the delay data at ``t-0.53``, we can deal this situation with
    the following methods:

    - ``"linear_interp"``: using linear interpolation to get the delay value
      at the required time (default).
    - ``"round"``: round the time to make it is the integer times of the time step. For
      the above situation, we will use the time at ``t-0.5`` to approximate the delay data
      at ``t-0.53``.

    .. versionadded:: 2.1.1

  See Also
  --------
  LengthDelay
  """

  def __init__(
      self,
      delay_target: Union[ndarray, jnp.ndarray],
      delay_len: Union[float, int],
      before_t0: Union[Callable, ndarray, jnp.ndarray, float, int] = None,
      t0: Union[float, int] = 0.,
      dt: Union[float, int] = None,
      name: str = None,
      interp_method: str = 'linear_interp',
  ):
    super(TimeDelay, self).__init__(name=name)

    # shape
    if not isinstance(delay_target, (jnp.ndarray, JaxArray)):
      raise ValueError(f'Must be an instance of JaxArray or jax.numpy.ndarray. But we got {type(delay_target)}')
    self.shape = delay_target.shape

    # delay_len
    self.t0 = t0
    self.dt = get_dt() if dt is None else dt
    check_float(delay_len, 'delay_len', allow_none=False, allow_int=True, min_bound=0.)
    self.delay_len = delay_len
    self.num_delay_step = int(jnp.ceil(self.delay_len / self.dt)) + 1

    # interp method
    if interp_method not in [_INTERP_LINEAR, _INTERP_ROUND]:
      raise UnsupportedError(f'Un-supported interpolation method {interp_method}, '
                             f'we only support: {[_INTERP_LINEAR, _INTERP_ROUND]}')
    self.interp_method = interp_method

    # time variables
    self.idx = Variable(jnp.asarray([0]))
    check_float(t0, 't0', allow_none=False, allow_int=True, )
    self.current_time = Variable(jnp.asarray([t0]))

    # delay data
    self.data = Variable(jnp.zeros((self.num_delay_step,) + self.shape, dtype=delay_target.dtype))
    if before_t0 is None:
      self._before_type = _DATA_BEFORE
    elif callable(before_t0):
      self._before_t0 = lambda t: bm.asarray(bm.broadcast_to(before_t0(t), self.shape),
                                             dtype=delay_target.dtype).value
      self._before_type = _FUNC_BEFORE
    elif isinstance(before_t0, (ndarray, jnp.ndarray, float, int)):
      self._before_type = _DATA_BEFORE
      self.data[:-1] = before_t0
    else:
      raise ValueError(f'"before_t0" does not support {type(before_t0)}')
    # set initial data
    self.data[-1] = delay_target

    # interpolation function
    self._interp_fun = jnp.interp
    for dim in range(1, len(self.shape) + 1, 1):
      self._interp_fun = vmap(self._interp_fun, in_axes=(None, None, dim), out_axes=dim - 1)

  def reset(self,
            delay_target,
            delay_len,
            t0: Union[float, int] = 0.,
            before_t0=None):
    """Reset the delay variable.

    Parameters
    ----------
    delay_target: JaxArray, ndarray, Variable
      The delay target.
    delay_len: float, int
      The maximum delay length. The unit is the time.
    t0: int, float
      The zero time.
    before_t0: int, float, ndarray, JaxArray
      The data before t0.
    """
    self.delay_len = delay_len
    self.num_delay_step = int(jnp.ceil(self.delay_len / self.dt)) + 1
    self.data.value = jnp.zeros((self.num_delay_step,) + self.shape,
                                dtype=delay_target.dtype)
    self.data[-1] = delay_target
    self.idx = Variable(jnp.asarray([0]))
    self.current_time = Variable(jnp.asarray([t0]))
    if before_t0 is not None:
      if not isinstance(before_t0, (ndarray, jnp.ndarray, float, int)):
        raise ValueError('Only support numerical values.')
      self.data[:-1] = before_t0
      self._before_type = _DATA_BEFORE

  def _check_time1(self, times):
    prev_time, current_time = times
    raise ValueError(f'The request time should be less than the '
                     f'current time {current_time}. But we '
                     f'got {prev_time} > {current_time}')

  def _check_time2(self, times):
    prev_time, current_time = times
    raise ValueError(f'The request time of the variable should be in '
                     f'[{current_time - self.delay_len}, {current_time}], '
                     f'but we got {prev_time}')

  def __call__(self, time, indices=None):
    # check
    if check.is_checking():
      current_time = self.current_time[0]
      check_error_in_jit(time > current_time + 1e-6, self._check_time1, (time, current_time))
      check_error_in_jit(time < current_time - self.delay_len - self.dt, self._check_time2, (time, current_time))
    if self._before_type == _FUNC_BEFORE:
      res = cond(time < self.t0,
                 self._before_t0,
                 self._after_t0,
                 time)
    else:
      res = self._after_t0(time)
    if indices is not None:  # TODO: indices is highly inefficient
      res = res[indices]
    return res

  def _after_t0(self, prev_time):
    diff = self.delay_len - (self.current_time[0] - prev_time)
    if isinstance(diff, ndarray):
      diff = diff.value
    if self.interp_method == _INTERP_LINEAR:
      req_num_step = jnp.asarray(diff / self.dt, dtype=jnp.int32)
      extra = diff - req_num_step * self.dt
      return cond(extra == 0., self._true_fn, self._false_fn, (req_num_step, extra))
    elif self.interp_method == _INTERP_ROUND:
      req_num_step = jnp.asarray(jnp.round(diff / self.dt), dtype=jnp.int32)
      return self._true_fn([req_num_step, 0.])
    else:
      raise UnsupportedError(f'Un-supported interpolation method {self.interp_method}, '
                             f'we only support: {[_INTERP_LINEAR, _INTERP_ROUND]}')

  def _true_fn(self, div_mod):
    req_num_step, extra = div_mod
    return self.data[self.idx[0] + req_num_step]

  def _false_fn(self, div_mod):
    req_num_step, extra = div_mod
    idx = jnp.asarray([self.idx[0] + req_num_step,
                       self.idx[0] + req_num_step + 1])
    idx %= self.num_delay_step
    return self._interp_fun(extra, jnp.asarray([0., self.dt]), self.data[idx])

  def update(self, time, value):
    self.data[self.idx[0]] = value
    self.current_time[0] = time
    self.idx.value = (self.idx + 1) % self.num_delay_step


class NeuTimeDelay(TimeDelay):
  """Neutral Time Delay. Alias of :py:class:`~.TimeDelay`."""
  pass


class LengthDelay(AbstractDelay):
  """Delay variable which has a fixed delay length.

  Parameters
  ----------
  delay_target: int, sequence of int
    The initial delay data.
  delay_len: int
    The maximum delay length.
  initial_delay_data: Tensor
    The delay data.
  name: str
    The delay object name.

  See Also
  --------
  TimeDelay
  """

  def __init__(
      self,
      delay_target: Union[ndarray, jnp.ndarray],
      delay_len: int,
      initial_delay_data: Union[float, int, bool, ndarray, jnp.ndarray, Callable] = None,
      name: str = None,
  ):
    super(LengthDelay, self).__init__(name=name)

    # attributes and variables
    self.num_delay_step: int = None
    self.shape: Tuple[int] = None
    self.idx: Variable = None
    self.data: Variable = None

    # initialization
    self.reset(delay_target, delay_len, initial_delay_data)

  def reset(
      self,
      delay_target,
      delay_len=None,
      initial_delay_data=None
  ):
    if not isinstance(delay_target, (ndarray, jnp.ndarray)):
      raise ValueError(f'Must be an instance of brainpy.math.ndarray '
                       f'or jax.numpy.ndarray. But we got {type(delay_target)}')
    self.shape = delay_target.shape

    # delay_len
    check_integer(delay_len, 'delay_len', allow_none=True, min_bound=0)
    if delay_len is None:
      if self.num_delay_step is None:
        raise ValueError('"delay_len" cannot be None.')
      delay_len = self.num_delay_step - 1
    self.num_delay_step = delay_len + 1

    # time variables
    if self.idx is None:
      self.idx = Variable(jnp.asarray([0], dtype=jnp.int32))
    else:
      self.idx.value = jnp.asarray([0], dtype=jnp.int32)

    # delay data
    if self.data is None:
      self.data = Variable(jnp.zeros((self.num_delay_step,) + self.shape, dtype=delay_target.dtype))
    else:
      self.data._value = jnp.zeros((self.num_delay_step,) + self.shape, dtype=delay_target.dtype)
    self.data[-1] = delay_target
    if initial_delay_data is None:
      pass
    elif isinstance(initial_delay_data, (ndarray, jnp.ndarray, float, int, bool)):
      self.data[:-1] = initial_delay_data
    elif callable(initial_delay_data):
      self.data[:-1] = initial_delay_data((delay_len,) + self.shape, dtype=delay_target.dtype)
    else:
      raise ValueError(f'"delay_data" does not support {type(initial_delay_data)}')

  def _check_delay(self, delay_len):
      raise ValueError(f'The request delay length should be less than the '
                       f'maximum delay {self.num_delay_step}. But we got {delay_len}')

  def __call__(self, delay_len, *indices):
    # check
    if check.is_checking():
      check_error_in_jit(bm.any(delay_len >= self.num_delay_step), self._check_delay, delay_len)
    # the delay length
    delay_idx = (self.idx[0] - delay_len - 1) % self.num_delay_step
    if not jnp.issubdtype(delay_idx.dtype, jnp.integer):
      raise ValueError(f'"delay_len" must be integer, but we got {delay_len}')
    # the delay data
    indices = (delay_idx, ) + tuple(indices)
    return self.data[indices]

  def update(self, value: Union[float, JaxArray, jnp.DeviceArray]):
    if jnp.shape(value) != self.shape:
      raise ValueError(f'value shape should be {self.shape}, but we got {jnp.shape(value)}')
    self.data[self.idx[0]] = value
    self.idx.value = (self.idx + 1) % self.num_delay_step


class NeuLenDelay(LengthDelay):
  """Neutral Length Delay. Alias of :py:class:`~.LengthDelay`."""
  pass
