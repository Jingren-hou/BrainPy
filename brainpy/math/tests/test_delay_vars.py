# -*- coding: utf-8 -*-

import unittest

import jax.numpy as jnp

import brainpy.math as bm


class TestTimeDelay(unittest.TestCase):
  def test_dim1(self):
    bm.enable_x64()

    # linear interp
    t0 = 0.
    before_t0 = jnp.repeat(jnp.arange(10).reshape((-1, 1)), 10, axis=1)
    delay = bm.TimeDelay(jnp.zeros(10), delay_len=1., t0=t0, dt=0.1, before_t0=before_t0)
    print(delay(t0 - 0.1))
    print(delay(t0 - 0.15))
    self.assertTrue(jnp.array_equal(delay(t0 - 0.1), jnp.ones(10) * 9.))
    self.assertTrue(jnp.array_equal(delay(t0 - 0.15), jnp.ones(10) * 8.5))
    print()
    print(delay(t0 - 0.23))
    print(delay(t0 - 0.23) - jnp.ones(10) * 8.7)
    # self.assertTrue(bm.array_equal(delay(t0 - 0.23), bm.ones(10) * 8.7))

    # round interp
    delay = bm.TimeDelay(jnp.zeros(10), delay_len=1., t0=t0, dt=0.1, before_t0=before_t0,
                         interp_method='round')
    self.assertTrue(jnp.array_equal(delay(t0 - 0.1), jnp.ones(10) * 9))
    print(delay(t0 - 0.15))
    self.assertTrue(jnp.array_equal(delay(t0 - 0.15), jnp.ones(10) * 8))
    self.assertTrue(jnp.array_equal(delay(t0 - 0.2), jnp.ones(10) * 8))

    bm.disable_x64()

  def test_dim2(self):
    t0 = 0.
    before_t0 = jnp.repeat(jnp.arange(10).reshape((-1, 1)), 10, axis=1)
    before_t0 = jnp.repeat(before_t0.reshape((10, 10, 1)), 5, axis=2)
    delay = bm.TimeDelay(jnp.zeros((10, 5)), delay_len=1., t0=t0, dt=0.1, before_t0=before_t0)
    self.assertTrue(jnp.array_equal(delay(t0 - 0.1), jnp.ones((10, 5)) * 9))
    self.assertTrue(jnp.array_equal(delay(t0 - 0.15), jnp.ones((10, 5)) * 8.5))
    # self.assertTrue(bm.array_equal(delay(t0 - 0.23), bm.ones((10, 5)) * 8.7))

  def test_dim3(self):
    t0 = 0.
    before_t0 = jnp.repeat(jnp.arange(10).reshape((-1, 1)), 10, axis=1)
    before_t0 = jnp.repeat(before_t0.reshape((10, 10, 1)), 5, axis=2)
    before_t0 = jnp.repeat(before_t0.reshape((10, 10, 5, 1)), 3, axis=3)
    delay = bm.TimeDelay(jnp.zeros((10, 5, 3)), delay_len=1., t0=t0, dt=0.1, before_t0=before_t0)
    self.assertTrue(jnp.array_equal(delay(t0 - 0.1), jnp.ones((10, 5, 3)) * 9))
    self.assertTrue(jnp.array_equal(delay(t0 - 0.15), jnp.ones((10, 5, 3)) * 8.5))
    # self.assertTrue(bm.array_equal(delay(t0 - 0.23), bm.ones((10, 5, 3)) * 8.7))

  def test1(self):
    print()
    delay = bm.TimeDelay(jnp.zeros(3), delay_len=1., dt=0.1, before_t0=lambda t: t)
    print(delay(-0.2))
    delay = bm.TimeDelay(jnp.zeros((3, 2)), delay_len=1., dt=0.1, before_t0=lambda t: t)
    print(delay(-0.6))
    delay = bm.TimeDelay(jnp.zeros((3, 2, 1)), delay_len=1., dt=0.1, before_t0=lambda t: t)
    print(delay(-0.8))

  def test_current_time2(self):
    print()
    delay = bm.TimeDelay(jnp.zeros(3), delay_len=1., dt=0.1, before_t0=lambda t: t)
    print(delay(0.))
    before_t0 = jnp.repeat(jnp.arange(10).reshape((-1, 1)), 10, axis=1)
    before_t0 = jnp.repeat(before_t0.reshape((10, 10, 1)), 5, axis=2)
    delay = bm.TimeDelay(jnp.zeros((10, 5)), delay_len=1., dt=0.1, before_t0=before_t0)
    print(delay(0.))

  # def test_prev_time_beyond_boundary(self):
  #   with self.assertRaises(ValueError):
  #     delay = bm.FixedLenDelay(3, delay_len=1., dt=0.1, before_t0=lambda t: t)
  #     delay(-1.2)


class TestLengthDelay(unittest.TestCase):
  def test1(self):
    dim = 3
    delay = bm.LengthDelay(jnp.zeros(dim), 10)
    print(delay(1))
    self.assertTrue(jnp.array_equal(delay(1), jnp.zeros(dim)))

    delay = bm.jit(delay)
    print(delay(1))
    self.assertTrue(jnp.array_equal(delay(1), jnp.zeros(dim)))

  def test2(self):
    dim = 3
    delay = bm.LengthDelay(jnp.zeros(dim), 10, initial_delay_data=jnp.arange(1, 11).reshape((10, 1)))
    print(delay(0))
    self.assertTrue(jnp.array_equal(delay(0), jnp.zeros(dim)))
    print(delay(1))
    self.assertTrue(jnp.array_equal(delay(1), jnp.ones(dim) * 10))

    delay = bm.jit(delay)
    print(delay(0))
    self.assertTrue(jnp.array_equal(delay(0), jnp.zeros(dim)))
    print(delay(1))
    self.assertTrue(jnp.array_equal(delay(1), jnp.ones(dim) * 10))

  def test3(self):
    dim = 3
    delay = bm.LengthDelay(jnp.zeros(dim), 10, initial_delay_data=jnp.arange(1, 11).reshape((10, 1)))
    print(delay(jnp.asarray([1, 2, 3]),
                jnp.arange(3)))
    # self.assertTrue(bm.array_equal(delay(0), bm.zeros(dim)))

    delay = bm.jit(delay)
    print(delay(jnp.asarray([1, 2, 3]),
                jnp.arange(3)))
    # self.assertTrue(bm.array_equal(delay(1), bm.ones(dim) * 10))
