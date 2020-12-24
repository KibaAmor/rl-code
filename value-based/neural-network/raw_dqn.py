from typing import Optional

import numpy as np
import torch
from torch.nn.functional import mse_loss
from utils.flappybird_wrapper import FlappyBirdWrapper, create_network
from utils.nnq_agent import NNQAgent


class RawDQNAgent(NNQAgent):
    def __init__(
        self,
        writer_name: str,
        *args,
        **kwargs,
    ):
        super().__init__(writer_name, *args, **kwargs)

        self.network = create_network(self.device)
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
    name = "raw_dqn"

    agent = RawDQNAgent(name)

    train_env = FlappyBirdWrapper(caption=name)
    test_env = FlappyBirdWrapper(caption=name, display_screen=True)
    load_cpkt = True
    total_episode = 100000
    max_step_per_episode = 1000
    episode_per_test = 10
    episode_per_save = 10

    agent.train_test(
        train_env,
        test_env,
        load_cpkt,
        total_episode,
        max_step_per_episode,
        episode_per_test,
        episode_per_save,
    )


if __name__ == "__main__":
    main()
