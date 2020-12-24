#!/usr/bin/python
# coding=utf-8
import os
from typing import Tuple

import cv2
import numpy as np
import pygame
import torch
from gym import Env, spaces
from PIL import Image
from ple import PLE
from ple.games import FlappyBird
from torch import nn


class FlappyBirdWrapper(Env):
    def __init__(
        self,
        caption="Flappy Bird",
        stack_num: int = 4,
        frame_size: Tuple[int, int] = (80, 80),
        display_screen: bool = False,
    ):
        self.game = FlappyBird()
        self.p = PLE(self.game, display_screen=display_screen)
        self.p.init()
        self.action_set = self.p.getActionSet()

        pygame.display.set_caption(caption)

        self.stack_num = stack_num
        self.frame_size = frame_size

        self.observation_space = spaces.Space((stack_num,) + frame_size)
        self.action_space = spaces.Discrete(2)

        empty_frame = np.zeros(frame_size, dtype=np.float32)
        self.obs = np.stack((empty_frame,) * stack_num, axis=0)

    def preprocess(self, obs: np.ndarray) -> np.ndarray:
        obs = cv2.resize(obs, self.frame_size)
        obs = cv2.cvtColor(obs, cv2.COLOR_RGB2GRAY)
        # _, obs = cv2.threshold(obs, 159, 255, cv2.THRESH_BINARY)
        obs = np.reshape(obs, (1,) + self.frame_size)
        obs = obs.astype(np.float32)
        return obs

    def _get_obs(self) -> np.ndarray:
        obs = self.p.getScreenRGB()
        obs = self.preprocess(obs)
        self.obs = np.concatenate((self.obs[1:, :, :], obs), axis=0)
        return self.obs

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, None]:
        reward = self.p.act(self.action_set[action])
        obs = self._get_obs()
        done = self.p.game_over()
        return obs, reward, done, None

    def reset(self) -> np.ndarray:
        self.p.reset_game()
        return self._get_obs()

    def save_screen(self, filename: str, preprocessed: bool = True) -> None:
        obs = self.p.getScreenRGB()
        if preprocessed:
            obs = self.preprocess(obs)[0].astype(np.uint8)
            obs = np.transpose(obs, axes=(1, 0))
        else:
            obs = np.transpose(obs, axes=(1, 0, 2))

        mode = "L" if preprocessed else "RGB"
        img = Image.fromarray(obs, mode)
        img.save(filename)


def create_network(device: torch.device) -> nn.Module:
    # input (, 80, 80)
    network = nn.Sequential(
        *[
            # (, 80, 80) => (32, 20, 20)
            nn.Conv2d(
                in_channels=4,
                out_channels=32,
                kernel_size=8,
                stride=4,
                padding=2,
            ),
            nn.SELU(inplace=True),
            # (32, 20, 20) => (32, 10, 10)
            nn.MaxPool2d(kernel_size=2),
            # (32, 10, 10) => (64, 5, 5)
            nn.Conv2d(
                in_channels=32, out_channels=64, kernel_size=4, stride=2, padding=1
            ),
            nn.SELU(inplace=True),
            # (64, 5, 5) => (64, 3, 3)
            nn.Conv2d(
                in_channels=64, out_channels=64, kernel_size=3, stride=1, padding=0
            ),
            nn.SELU(inplace=True),
            # (64, 3, 3) => (64, 2, 2)
            nn.MaxPool2d(kernel_size=2, padding=1),
            # (64, 2, 2) => 256
            nn.Flatten(),
            # (256,) => (256,)
            nn.Linear(256, 256),
            nn.SELU(inplace=True),
            # (256,) => (256,)
            nn.Linear(256, 256),
            # (256,) => (2,)
            nn.Linear(256, 2),
        ]
    )
    network.to(device)
    return network


def main():
    import pathlib

    here = pathlib.Path(__file__).parent.resolve()
    saved_screen = os.path.join(here, "saved_screen")
    if not os.path.isdir(saved_screen):
        os.mkdir(saved_screen)

    env = FlappyBirdWrapper()
    env.reset()

    # skip some frame
    for _ in range(20):
        env.step(np.random.randint(env.action_space.n))

    env.save_screen(f"{saved_screen}/flappybird.png", False)
    env.save_screen(f"{saved_screen}/preprocessed_flappybird.png", True)


if __name__ == "__main__":
    main()
