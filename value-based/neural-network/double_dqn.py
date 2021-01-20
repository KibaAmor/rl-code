import pathlib
from argparse import ArgumentParser
from copy import deepcopy
from os.path import join
from typing import Callable, Optional

import numpy as np
import torch
from torch import nn
from torch.utils.tensorboard import SummaryWriter
from utils.buffer import ReplayBuffer
from utils.misc import Policy, train, watch
from utils.utils import create_collector, create_network, create_tester, get_arg_parser


class DoubleDQNPolicy(Policy):
    def __init__(
        self,
        network: nn.Module,
        optimizer: torch.optim.Optimizer,
        gamma: float,
        target_network: nn.Module,
        target_update_freq: int,
        tau: float,
    ):
        super().__init__(network, optimizer, gamma)
        self.target_network = target_network.to(self.device)
        self.target_network.load_state_dict(self.network.state_dict())

        self.target_update_freq = target_update_freq
        self.tau = tau
        self.update_count = 0

    def compute_target_q(
        self,
        next_obss: torch.FloatTensor,
        rews: torch.FloatTensor,
        dones: torch.LongTensor,
    ) -> torch.FloatTensor:
        with torch.no_grad():
            acts_star = self.network(next_obss).argmax(-1).unsqueeze(1)
            qval_max = self.target_network(next_obss).gather(1, acts_star).squeeze()
        qval_targ = rews + (1 - dones) * self.gamma * qval_max
        return qval_targ

    def update(self, buffer: ReplayBuffer) -> dict:
        info = super().update(buffer)

        self.update_count += 1
        if self.update_count >= self.target_update_freq:
            self.update_count -= self.target_update_freq
            self.soft_update_target()

        return info

    def soft_update_target(self) -> None:
        for target_param, local_param in zip(
            self.target_network.parameters(), self.network.parameters()
        ):
            target_param.data.copy_(
                self.tau * local_param.data + (1.0 - self.tau) * target_param.data
            )


def get_args(parser_hook: Optional[Callable[[ArgumentParser], None]] = None):
    parser = get_arg_parser("double-dqn")
    parser.add_argument(
        "--target-update-freq",
        type=int,
        default=32,
        metavar="N",
        help="target network update frequency",
    )
    parser.add_argument(
        "--tau",
        type=float,
        default=1.0,
        metavar="TAU",
        help="target network soft update parameters",
    )
    if parser_hook is not None:
        parser_hook(parser)
    args = parser.parse_args()
    return args


def create_policy(args) -> Policy:
    network = create_network(args)
    target_network = create_network(args)
    optimizer = torch.optim.Adam(network.parameters(), lr=args.lr)
    policy = DoubleDQNPolicy(
        network,
        optimizer,
        args.gamma,
        target_network,
        args.target_update_freq,
        args.tau,
    )

    if args.ckpt is not None:
        policy.load_state_dict(torch.load(args.ckpt))
        print(f"load checkpoint policy from file '{args.ckpt}'")

    return policy


def train_double_dqn(args) -> None:
    print(dict(**args.__dict__))

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    policy = create_policy(args)

    here = pathlib.Path(__file__).parent.resolve()
    logdir = join(here, args.name)
    writer = SummaryWriter(logdir)

    def precollect(
        policy: DoubleDQNPolicy, epoch: int, steps: int, updates: int
    ) -> None:
        eps = args.eps_collect * (args.eps_collect_gamma ** epoch)
        policy.eps = eps if eps > args.eps_collect_min else args.eps_collect_min
        writer.add_scalar("0_train/eps", policy.eps, steps)

    def preupdate(
        policy: DoubleDQNPolicy, epoch: int, steps: int, updates: int
    ) -> None:
        policy.eps = 0.0

    def pretest(policy: DoubleDQNPolicy, epoch: int, steps: int, updates: int) -> None:
        policy.eps = args.eps_test

    def save(policy: DoubleDQNPolicy, epoch: int, best_rew: float, rew: float) -> bool:
        if rew <= best_rew:
            return True
        policy = deepcopy(policy).to(torch.device("cpu"))
        torch.save(policy.state_dict(), f"{logdir}/dqn_{args.game}_{rew:.2f}.pth")
        if args.max_reward is not None:
            return rew < args.max_reward
        return True

    collector = create_collector(args)
    tester = create_tester(args)

    best_rew = train(
        writer,
        policy,
        collector,
        tester,
        args.warmup_size,
        args.epochs,
        args.step_per_epoch,
        args.collect_per_step,
        args.update_per_step,
        args.batch_size,
        max_loss=args.max_loss,
        precollect_fn=precollect,
        preupdate_fn=preupdate,
        pretest_fn=pretest,
        save_fn=save,
    )
    print(f"best rewards: {best_rew}")


def watch_double_dqn(args) -> None:
    policy = create_policy(args)
    tester = create_tester(args)
    watch(policy, tester, args.epochs)


if __name__ == "__main__":
    args = get_args()
    if args.watch:
        watch_double_dqn(args)
    else:
        train_double_dqn(args)
