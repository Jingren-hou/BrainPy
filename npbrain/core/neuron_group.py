# -*- coding: utf-8 -*-

from copy import deepcopy

from .common_func import BaseType
from .. import _numpy as bnp
from .. import profile
from ..utils.helper import Dict

__all__ = [
    'NeuGroup',
]


class NeuGroup(BaseType):
    """Neuron Group.
    """
    def __init__(self, create_func, name=None):
        super(NeuGroup, self).__init__(create_func=create_func, name=name, type_='neu')

    def __call__(self, geometry, monitors=None, vars_init=None, pars_update=None):
        # num and geometry
        # -----------------
        if isinstance(geometry, (int, float)):
            geometry = (1, int(geometry))
        elif isinstance(geometry, (tuple, list)):
            if len(geometry) == 1:
                height, width = 1, geometry[0]
            elif len(geometry) == 2:
                height, width = geometry[0], geometry[1]
            else:
                raise ValueError('Do not support 3+ dimensional networks.')
            geometry = (height, width)
        else:
            raise ValueError()
        num = int(bnp.prod(geometry))
        self.num = num
        self.geometry = geometry

        # variables and "state" ("S")
        # ----------------------------
        assert isinstance(vars_init, dict), '"vars_init" must be a dict.'
        variables = deepcopy(self.variables)
        for k, v in vars_init:
            if k not in self.variables:
                raise KeyError(f'variable "{k}" is not defined in "{self.name}".')
            variables[k] = v

        if profile.is_numba_bk():
            self.var2index = Dict()
            self.state = Dict()
            self._state_mat = bnp.zeros((len(variables), num), dtype=bnp.float_)
            for i, (k, v) in enumerate(variables.items()):
                self._state_mat[i] = v
                self.state[k] = self._state_mat[i]
                self.var2index[k] = i
        else:
            self.var2index = None
            self.state = Dict()
            for k, v in variables.items():
                self.state[k] = bnp.ones(num, dtype=bnp.float_) * v
        self.S = self.state

        # parameters and "P"
        # -------------------
        assert isinstance(pars_update, dict), '"pars_update" must be a dict.'
        parameters = deepcopy(self.parameters)
        for k, v in pars_update:
            val_size = bnp.size(v)
            if val_size != 1:
                if val_size != num:
                    raise ValueError(f'The size of parameter "{k}" is wrong, "{val_size}" != 1 '
                                     f'and "{val_size}" != {num}.')
            parameters[k] = v
        if profile.is_numba_bk():
            import numba as nb
            max_size = max([bnp.size(v) for v in parameters.values()])
            if max_size > 1:
                self.P = nb.typed.Dict(key_type=nb.types.unicode_type, value_type=nb.types.float_[:])
                for k, v in parameters.items():
                    self.P[k] = bnp.ones(self.num, dtype=bnp.float_) * v
                self.parameters = self.P
            else:
                self.P = nb.typed.Dict(key_type=nb.types.unicode_type, value_type=nb.types.float_)
                for k, v in parameters.items():
                    self.P[k] = v
                self.parameters = self.P
        else:
            self.P = self.parameters = parameters

        # define update functions
        # -------------------------
        self.func_returns = self.create_func(**parameters)
        step_funcs = self.func_returns['step_funcs']
        if callable(step_funcs):
            self.update_funcs = [step_funcs, ]
        elif isinstance(step_funcs, (tuple, list)):
            self.update_funcs = list(step_funcs)
        else:
            raise ValueError('"step_funcs" must be a callable, or a list/tuple of callable functions.')

        # monitors
        # ----------
        self.mon = Dict()
        self._mon_vars = monitors
        self._mon_update = None

        if monitors is not None:
            for k in monitors:
                self.mon[k] = bnp.zeros((1, 1), dtype=bnp.float_)

            # generate function
            def update(i):
                for k in self._mon_vars:
                    self.mon[k][i] = self.state[k]

            self._mon_update = update
            self.update_funcs.append(update)

        # update functions
        # -----------------
        self.update_funcs = tuple(self.update_funcs)

