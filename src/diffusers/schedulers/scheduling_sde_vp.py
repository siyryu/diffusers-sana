# Copyright 2022 Google Brain and The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# DISCLAIMER: This file is strongly influenced by https://github.com/yang-song/score_sde_pytorch

import math
from typing import Union

import torch

from ..configuration_utils import ConfigMixin, register_to_config
from ..utils import deprecate
from .scheduling_utils import SchedulerMixin


class ScoreSdeVpScheduler(SchedulerMixin, ConfigMixin):
    """
    The variance preserving stochastic differential equation (SDE) scheduler.

    [`~ConfigMixin`] takes care of storing all config attributes that are passed in the scheduler's `__init__`
    function, such as `num_train_timesteps`. They can be accessed via `scheduler.config.num_train_timesteps`.
    [`~ConfigMixin`] also provides general loading and saving functionality via the [`~ConfigMixin.save_config`] and
    [`~ConfigMixin.from_config`] functions.

    For more information, see the original paper: https://arxiv.org/abs/2011.13456

    UNDER CONSTRUCTION

    """

    @register_to_config
    def __init__(self, num_train_timesteps=2000, beta_min=0.1, beta_max=20, sampling_eps=1e-3, **kwargs):
        deprecate(
            "tensor_format",
            "0.5.0",
            "If you're running your code in PyTorch, you can safely remove this argument.",
            take_from=kwargs,
        )
        self.sigmas = None
        self.discrete_sigmas = None
        self.timesteps = None

    def set_timesteps(self, num_inference_steps, device: Union[str, torch.device] = None):
        self.timesteps = torch.linspace(1, self.config.sampling_eps, num_inference_steps, device=device)

    def step_pred(self, score, x, t, generator=None):
        if self.timesteps is None:
            raise ValueError(
                "`self.timesteps` is not set, you need to run 'set_timesteps' after creating the scheduler"
            )

        # TODO(Patrick) better comments + non-PyTorch
        # postprocess model score
        log_mean_coeff = (
            -0.25 * t**2 * (self.config.beta_max - self.config.beta_min) - 0.5 * t * self.config.beta_min
        )
        std = torch.sqrt(1.0 - torch.exp(2.0 * log_mean_coeff))
        std = std.flatten()
        while len(std.shape) < len(score.shape):
            std = std.unsqueeze(-1)
        score = -score / std

        # compute
        dt = -1.0 / len(self.timesteps)

        beta_t = self.config.beta_min + t * (self.config.beta_max - self.config.beta_min)
        beta_t = beta_t.flatten()
        while len(beta_t.shape) < len(x.shape):
            beta_t = beta_t.unsqueeze(-1)
        drift = -0.5 * beta_t * x

        diffusion = torch.sqrt(beta_t)
        drift = drift - diffusion**2 * score
        x_mean = x + drift * dt

        # add noise
        noise = torch.randn(x.shape, layout=x.layout, generator=generator).to(x.device)
        x = x_mean + diffusion * math.sqrt(-dt) * noise

        return x, x_mean

    def __len__(self):
        return self.config.num_train_timesteps
