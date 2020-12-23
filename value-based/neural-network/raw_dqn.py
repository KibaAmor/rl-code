from typing import Optional

import numpy as np
import torch
from gym.spaces import Discrete, Space
from torch import nn
from torch.nn.functional import mse_loss
from utils.agent import Agent
from utils.flappybird_wrapper import FlappyBirdWrapper


class RawDQNAgent(Agent):
    def __init__(
        self,
        obs_space: Space,
        act_space: Discrete,
        writer_name: str,
        *args,
        **kwargs,
    ):
        super().__init__(writer_name, *args, **kwargs)

        # input (, 80, 80)
        self.network = nn.Sequential(
            *[
                # (, 80, 80) => (32, 40, 40)
                nn.Conv2d(
                    in_channels=obs_space.shape[0],
                    out_channels=32,
                    kernel_size=7,
                    padding=3,
                ),
                nn.Conv2d(in_channels=32, out_channels=32, kernel_size=7, padding=3),
                nn.SELU(inplace=True),
                nn.MaxPool2d(kernel_size=2),
                # (32, 40, 40) => (64, 20, 20)
                nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, padding=1),
                nn.Conv2d(in_channels=64, out_channels=64, kernel_size=3, padding=1),
                nn.SELU(inplace=True),
                nn.MaxPool2d(kernel_size=2),
                # (64, 20, 20) => 25600
                nn.Flatten(),
                # (25600,) => (128,)
                nn.Linear(25600, 128),
                nn.SELU(inplace=True),
                # (128,) => (act_space.n,)
                nn.Linear(128, act_space.n),
            ]
        )
        self.network.to(self.device)
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=self.lr)

    def learn(
        self,
        episode: int,
        obs: np.ndarray,
        act: int,
        reward: float,
        next_obs: np.ndarray,
        done: bool,
    ) -> Optional[float]:
        obs = torch.from_numpy(obs).to(self.device)
        obs.unsqueeze_(0)
        next_obs = torch.from_numpy(next_obs).to(self.device)
        next_obs.unsqueeze_(0)

        qvalue_predict = self.network(obs)[0][act]

        qvalue_max = self._predict_qvalue(next_obs, 0)[0].max()
        qvalue_target = reward + (1 - np.int(done)) * self.gamma * qvalue_max

        loss = mse_loss(qvalue_predict, qvalue_target)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        return loss.item()


def main():
    train_env = FlappyBirdWrapper()
    test_env = FlappyBirdWrapper(display_screen=True)
    writer_name = "raw_dqn"
    agent = RawDQNAgent(
        train_env.observation_space, train_env.action_space, writer_name
    )

    agent.train_test(train_env, test_env)


if __name__ == "__main__":
    main()
