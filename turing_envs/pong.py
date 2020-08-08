import numpy as np
import pygame
import gym
from gym.utils import seeding


class Bar:
    def __init__(self, x, y, screen_width, screen_height,
                 length=20, width=2, velocity=2, horizontal=True, np_random=np.random):
        self.np_random = np_random
        self.x = int(x)
        self.y = int(y)
        self.length = length
        self.width = width
        self.velocity = velocity
        self.horizontal = horizontal
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._direction = 0

    def draw(self, screen, color=(255, 255, 255)):  # desenhar em pygame
        pygame.draw.rect(screen, color, (
                         self.x-self.width/2, self.y-self.length/2, self.width, self.length))

    # mode = (human, machine, enemy); move = (0,1,2)
    def move(self, mode='human', move=None, ball=None):
        lookup_table = {pygame.K_s: lambda x: x + self.velocity,
                        1: lambda x: x + self.velocity,  # movimentamos a barra verticalmente
                        pygame.K_w: lambda x: x - self.velocity,
                        2: lambda x: x - self.velocity}  # conforme a tabela indica

        # modos de movimento: o mode 'human' serve para o controle manual,
        # 'machine' diz respeito ao environment e o 'enemy' serve para controlar
        # a barra inimiga
        if mode == 'human':
            pressed = pygame.key.get_pressed()
            for k in lookup_table.keys():  # verificamos se a tecla foi apertada
                if pressed[k]:
                    self.y = lookup_table[k](self.y)

        elif mode == 'machine':
            if move != 0:
                self.y = lookup_table[move](self.y)

        elif mode == 'enemy':
            if self._direction != 0:
                if self.np_random.random() < .08:
                    self._direction = 0
            elif ball.x >= self.screen_width*.6 and self.np_random.random() < .85:
                self._direction = np.sign(ball.y - self.y)
            self.y += self.velocity*self._direction

        self.y = np.clip(self.y, 0, self.screen_height)


class Ball:
    def __init__(self, x, y, size, velocity=1, np_random=np.random):
        self.np_random = np_random
        self.x = int(x)
        self.y = int(y)
        self.size = size
        self.abs_velocity = velocity
        self.reset_velocity()

    def reset_velocity(self):
        v = self.abs_velocity
        direction = self.np_random.uniform(np.pi/8, np.pi/3)  # first quadrant
        direction *= self.np_random.choice([-1, 1])  # right side
        direction += self.np_random.choice([0, np.pi])  # left side
        self.velocity = [
            v*np.cos(direction), -v*np.sin(direction)]

    def move(self):
        self.x += self.velocity[0]
        self.y += self.velocity[1]

    def draw(self, screen, color=(255, 255, 255)):
        pygame.draw.rect(screen, color, (
            self.x - self.size, self.y - self.size, 2*self.size, 2*self.size))

    def bounce(self, wall):
        lookup_table = {False: [-1, 1],
                        True: [1, -1]}
        if abs(self.x - wall.x) < (wall.width/2 + self.size - 1) \
                and abs(self.y - wall.y) < (wall.length/2 + self.size):
            self.velocity[0] *= lookup_table[wall.horizontal][0]
            self.velocity[1] *= lookup_table[wall.horizontal][1]
            return True
        return False


class PongEnv(gym.Env):
    _gym_disable_underscore_compat = True
    metadata = {'render.modes': ['human']}
    reward_range = (-float('inf'), float('inf'))
    action_space = gym.spaces.Discrete(3)
    observation_space = gym.spaces.Box(
        low=-np.float32('inf'), high=np.float32('inf'), shape=(4,))

    def __init__(self, height=300, width=400, repeat_actions=3,
                 bar_velocity=3, ball_velocity=2,
                 num_matches=7, fps=50):

        self.observation_space = gym.spaces.Box(
            low=np.array([0, 0, 0, 0]),
            high=np.array([width, height, width, height]),
            dtype=np.float32)

        self.height = height
        self.width = width
        self.rendered = False
        self.num_matches = num_matches
        self.fps = fps
        self.clock = pygame.time.Clock()
        self.repeat_actions = repeat_actions

        param_names = ['x', 'y', 'length', 'width', 'velocity', 'horizontal']
        w, h, vel = width, height, bar_velocity
        bar_parameters = [
            # (x,    y,   len, width, vel, horizontal)
            (w/27,   h/2, h/3, w/50, vel, False),  # jogador
            (w-w/27, h/2, h/3, w/50, vel, False),  # oponente
            (w/2,    0,   5,   w,    0,   True),   # teto
            (w/2,    h,   5,   w,    0,   True),   # chão
            (0,      h/2, h,   5,    0,   False),  # parede esq.
            (w,      h/2, h,   5,    0,   False),  # parede dir.
        ]
        # Obs: as paredes esquerda e direita têm propósito puramente estético

        self.bars = []
        for bar in bar_parameters:
            kwargs = dict(zip(param_names, bar))
            self.bars.append(
                Bar(screen_width=width, screen_height=height, **kwargs))

        self.control_bar = self.bars[0]
        self.other_bar = self.bars[1]
        self.left_wall = self.bars[4]
        self.right_wall = self.bars[5]

        self.ball = Ball(x=width/2, y=height/2, size=10,
                         velocity=ball_velocity)

        self.seed()

    def reset_match(self):
        self.ball.x, self.ball.y = self.width/2, self.height/2
        self.control_bar.y = self.height/2
        self.other_bar.y = self.height/2
        self.ball.reset_velocity()

    def _get_state(self):
        return np.array([self.control_bar.x, self.control_bar.y,
                         self.ball.x, self.ball.y])

    def reset(self):
        self.reset_match()
        self.done = False
        self.score = [0, 0]
        return self._get_state()

    def step(self, action):
        reward = 0
        for _ in range(self.repeat_actions):
            reward += self._step(action)
            if self.done:
                break
        return self._get_state(), reward, self.done, {}

    def _step(self, action):
        if self.done:
            return

        self.control_bar.move(mode='machine', move=action)
        self.other_bar.move(mode='enemy', ball=self.ball)
        self.ball.move()

        for bar in self.bars:
            self.ball.bounce(bar)

        if self.ball.bounce(self.left_wall):
            player_scored = False
            self.score[1] += 1
        elif self.ball.bounce(self.right_wall):
            player_scored = True
            self.score[0] += 1
        else:  # no points
            return 0

        reward = 500
        if max(self.score) > self.num_matches / 2:
            self.done = True
            reward += 2000
        self.reset_match()
        return reward if player_scored else -reward

    def render(self, mode='human', wait=True):
        if mode != 'human':
            return super().render(mode=mode)

        if not self.rendered:
            self.screen = pygame.display.set_mode((self.width, self.height))
            self.rendered = True
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.done = True
        self.screen.fill((20, 20, 20))
        for bar in self.bars:
            bar.draw(self.screen)
        self.ball.draw(self.screen)
        pygame.display.set_caption(f'Pong - {self.score[0]} x {self.score[1]}')
        pygame.display.update()
        if wait:
            self.clock.tick(self.fps)

    def close(self):
        # TODO: verificar isso
        pygame.display.iconify()

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        self.ball.np_random = self.np_random
        for bar in self.bars:
            bar.np_random = self.np_random
        return [seed]


class EasyPongEnv(PongEnv):
    observation_space = gym.spaces.Box(
        low=-np.float32('inf'), high=np.float32('inf'), shape=(2,))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        low = self.observation_space.low
        high = self.observation_space.high
        self.observation_space = gym.spaces.Box(
            low=np.array([low[0] - high[2], low[1] - high[3]]),
            high=np.array([high[0] - low[2], high[1] - low[3]]),
            dtype=np.float32)

    def _get_state(self):
        dx = self.control_bar.x - self.ball.x  # s[0] - s[2]
        dy = self.control_bar.y - self.ball.y  # s[1] - s[3]
        return np.array([dx, dy])
